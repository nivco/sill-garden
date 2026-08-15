#!/usr/bin/env python3
"""Sill Garden scorecard → products/analytics/latest.json

Hero KPIs: sessions, page views, affiliate clicks, GSC, YouTube, Amazon (manual).
Run: python scripts/analytics_summary.py
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "products" / "analytics"
LATEST = OUT_DIR / "latest.json"
HISTORY = OUT_DIR / "history.json"
AMAZON_MANUAL = OUT_DIR / "amazon-manual.json"
YOUTUBE_ACCESS = ROOT / "products" / "youtube" / "youtube-access-status.json"
ACTION_QUEUE = ROOT / "products" / "traffic" / "action-queue.json"
SITE_URL = "https://sillgarden.com"


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def http_json(url: str, *, method: str = "GET", headers: dict | None = None, body: dict | None = None) -> dict:
    data = None
    hdrs = {"User-Agent": "SillGarden-Analytics/1.0", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HTTP {exc.code} {url}: {err_body}") from exc


def probe_site() -> dict:
    try:
        req = urllib.request.Request(SITE_URL + "/", headers={"User-Agent": "SillGarden-Analytics/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"ok": 200 <= resp.status < 400, "status": resp.status, "url": SITE_URL}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": None, "url": SITE_URL, "error": str(exc)[:200]}


OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]


def resolve_path(raw: str) -> Path | None:
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = (ROOT / p).resolve()
        if not p.is_file():
            alt = (ROOT.parent / raw).resolve()
            if alt.is_file():
                p = alt
    return p if p.is_file() else None


def materialize_json_env(env_name: str, filename: str) -> Path | None:
    """Local path, or write JSON secret content from env (GitHub Actions)."""
    import tempfile

    raw = (os.environ.get(env_name) or "").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        tmp_dir = os.environ.get("RUNNER_TEMP") or os.environ.get("TEMP") or tempfile.gettempdir()
        path = Path(tmp_dir) / filename
        path.write_text(json.dumps(json.loads(raw), indent=2), encoding="utf-8")
        return path
    return resolve_path(raw)


def google_token(scopes: list[str]) -> str:
    """Service account or OAuth (same env pattern as Maker Tool Stack)."""
    auth_mode = (os.environ.get("GOOGLE_AUTH") or "sa").strip().lower()
    if auth_mode == "oauth":
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        token_path = materialize_json_env("GOOGLE_USER_TOKEN_JSON", "sill-google-user-token.json")
        client_path = materialize_json_env("GOOGLE_OAUTH_CLIENT_JSON", "sill-google-oauth-client.json")
        # Fall back to MTS secrets
        if not token_path:
            token_path = resolve_path("../makertoolstack/secrets/google-user-token.json")
        if not client_path:
            client_path = resolve_path("../makertoolstack/secrets/google-oauth-client.json")
        if not token_path or not client_path:
            raise RuntimeError("OAuth mode needs GOOGLE_USER_TOKEN_JSON + GOOGLE_OAUTH_CLIENT_JSON")
        # Always load with both scopes so a GA4-only refresh cannot drop GSC.
        creds = Credentials.from_authorized_user_file(str(token_path), scopes=OAUTH_SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                data = json.loads(creds.to_json())
                data["scopes"] = sorted(set(data.get("scopes") or []) | set(OAUTH_SCOPES))
                token_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                raise RuntimeError("OAuth token invalid — re-auth via MTS google oauth flow")
        if any("webmasters" in s for s in scopes):
            granted = set(creds.scopes or [])
            if not any("webmasters" in s for s in granted):
                raise RuntimeError("OAuth token missing Search Console scope — re-run google_oauth_login.py --force")
        return creds.token

    sa_path = materialize_json_env("GOOGLE_SERVICE_ACCOUNT_JSON", "sill-google-sa.json")
    if not sa_path:
        sa_path = resolve_path("../makertoolstack/secrets/google-sa.json")
    if not sa_path:
        for cand in (
            "../makertoolstack/secrets/service-account.json",
            "../makertoolstack/secrets/ga4-service-account.json",
            "../makertoolstack/secrets/google-service-account.json",
        ):
            sa_path = resolve_path(cand)
            if sa_path:
                break
    if not sa_path:
        raise RuntimeError("Set GOOGLE_SERVICE_ACCOUNT_JSON (or reuse MTS secrets path)")

    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_file(str(sa_path), scopes=scopes)
    from google.auth.transport.requests import Request

    creds.refresh(Request())
    return creds.token


def ga4_run_report(token: str, property_id: str, body: dict) -> dict:
    pid = property_id.strip()
    if not pid.startswith("properties/"):
        pid = f"properties/{pid}"
    return http_json(
        f"https://analyticsdata.googleapis.com/v1beta/{pid}:runReport",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
        body=body,
    )


NETWORK_BY_HOST = (
    ("amazon.", "Amazon Associates"),
    ("clickandgrow.", "Click & Grow"),
    ("gardeners.", "Gardener's Supply"),
)


def network_for_link(link: str) -> str:
    """Map an outbound affiliate URL (or bare domain) to a program name."""
    host = link.strip().lower()
    if "://" in host:
        host = urllib.parse.urlparse(host).netloc
    host = host.replace("www.", "")
    for needle, name in NETWORK_BY_HOST:
        if needle in host:
            return name
    return host or "Other"


def ga4_metric_value(report: dict, name: str) -> float:
    headers = [h.get("name") for h in report.get("metricHeaders", [])]
    rows = report.get("rows") or []
    if not rows or name not in headers:
        return 0.0
    idx = headers.index(name)
    return float(rows[0]["metricValues"][idx]["value"])


def fetch_ga4(property_id: str) -> dict:
    token = google_token(["https://www.googleapis.com/auth/analytics.readonly"])
    range_7d = [{"startDate": "7daysAgo", "endDate": "today"}]

    totals_report = ga4_run_report(
        token,
        property_id,
        {
            "dateRanges": range_7d,
            "metrics": [
                {"name": "activeUsers"},
                {"name": "sessions"},
                {"name": "screenPageViews"},
                {"name": "engagedSessions"},
                {"name": "averageSessionDuration"},
                {"name": "engagementRate"},
            ],
        },
    )
    totals = {
        "activeUsers": int(ga4_metric_value(totals_report, "activeUsers")),
        "sessions": int(ga4_metric_value(totals_report, "sessions")),
        "screenPageViews": int(ga4_metric_value(totals_report, "screenPageViews")),
        "engagedSessions": int(ga4_metric_value(totals_report, "engagedSessions")),
        "averageSessionDuration_sec": round(ga4_metric_value(totals_report, "averageSessionDuration"), 1),
        "engagementRate_pct": round(ga4_metric_value(totals_report, "engagementRate") * 100, 1),
    }

    def dim_rows(body: dict, limit: int = 10) -> list[dict]:
        report = ga4_run_report(token, property_id, body)
        d_headers = [h.get("name") for h in report.get("dimensionHeaders", [])]
        m_headers = [h.get("name") for h in report.get("metricHeaders", [])]
        out = []
        for row in (report.get("rows") or [])[:limit]:
            dims = [d.get("value") for d in row.get("dimensionValues", [])]
            mets = [m.get("value") for m in row.get("metricValues", [])]
            out.append(dict(zip(d_headers + m_headers, dims + mets, strict=False)))
        return out

    top_pages = dim_rows(
        {
            "dateRanges": range_7d,
            "metrics": [{"name": "sessions"}, {"name": "screenPageViews"}],
            "dimensions": [{"name": "pagePath"}],
            "limit": 12,
            "orderBys": [{"desc": True, "metric": {"metricName": "sessions"}}],
        }
    )
    channels = dim_rows(
        {
            "dateRanges": range_7d,
            "metrics": [{"name": "sessions"}],
            "dimensions": [{"name": "sessionDefaultChannelGroup"}],
            "limit": 8,
            "orderBys": [{"desc": True, "metric": {"metricName": "sessions"}}],
        }
    )
    source_medium = dim_rows(
        {
            "dateRanges": range_7d,
            "metrics": [{"name": "sessions"}, {"name": "engagedSessions"}],
            "dimensions": [{"name": "sessionSourceMedium"}],
            "limit": 12,
            "orderBys": [{"desc": True, "metric": {"metricName": "sessions"}}],
        },
        limit=12,
    )

    # Affiliate events. Network-specific event names avoid requiring GA4 custom dimensions.
    affiliate_event_names = [
        "affiliate_click",
        "affiliate_click_amazon",
        "affiliate_click_click_grow",
        "affiliate_click_gardeners_supply",
        "outbound_click",
    ]
    events_report = ga4_run_report(
        token,
        property_id,
        {
            "dateRanges": range_7d,
            "metrics": [{"name": "eventCount"}],
            "dimensions": [{"name": "eventName"}],
            "dimensionFilter": {
                "filter": {
                    "fieldName": "eventName",
                    "inListFilter": {"values": affiliate_event_names},
                }
            },
        },
    )
    events: dict[str, int] = {}
    for row in events_report.get("rows") or []:
        name = row["dimensionValues"][0]["value"]
        count = int(float(row["metricValues"][0]["value"]))
        events[name] = count
    networks_from_events = {
        "Amazon Associates": events.get("affiliate_click_amazon", 0),
        "Click & Grow": events.get("affiliate_click_click_grow", 0),
        "Gardener's Supply": events.get("affiliate_click_gardeners_supply", 0),
    }

    # Per-link clicks: GA4 registers event params under different dimension names.
    link_rows: list[dict] = []
    link_dim_used = None
    for dim in (
        "customEvent:link_url",
        "link_url",
        "customEvent:linkUrl",
        "linkUrl",
        "customEvent:link_domain",
        "link_domain",
    ):
        try:
            link_report = ga4_run_report(
                token,
                property_id,
                {
                    "dateRanges": range_7d,
                    "metrics": [{"name": "eventCount"}],
                    "dimensions": [{"name": dim}],
                    "dimensionFilter": {
                        "filter": {
                            "fieldName": "eventName",
                            "stringFilter": {"matchType": "EXACT", "value": "affiliate_click"},
                        }
                    },
                    "limit": 15,
                    "orderBys": [{"desc": True, "metric": {"metricName": "eventCount"}}],
                },
            )
        except Exception:  # noqa: BLE001
            continue
        rows: list[dict] = []
        for row in link_report.get("rows") or []:
            link = (row.get("dimensionValues") or [{}])[0].get("value") or ""
            count = int(float((row.get("metricValues") or [{}])[0].get("value") or 0))
            if link and link not in ("(not set)", "(none)") and count:
                rows.append(
                    {
                        "link_url": link,
                        "clicks": count,
                        "network": network_for_link(link),
                    }
                )
        if rows:
            link_rows = rows
            link_dim_used = dim
            break
    if not link_rows:
        if int(events.get("affiliate_click") or 0) > 0:
            link_rows = [
                {
                    "note": (
                        "affiliate_click events exist, but no reportable link_url/link_domain "
                        "dimension yet. Register link_url as a GA4 custom dimension or wait "
                        "for more attributed events."
                    )
                }
            ]
        else:
            link_rows = [{"note": "No affiliate_click events in the last 7 days"}]

    # Network-specific events only exist for clicks after the tagging deploy; older clicks
    # are still attributable through the destination URL.
    networks_from_links: dict[str, int] = {}
    for row in link_rows:
        if not row.get("link_url"):
            continue
        networks_from_links[row["network"]] = networks_from_links.get(row["network"], 0) + row["clicks"]

    if any(networks_from_events.values()):
        affiliate_networks = dict(networks_from_events)
        attribution_source = "network_events"
        for name, count in networks_from_links.items():
            affiliate_networks[name] = max(affiliate_networks.get(name, 0), count)
    elif networks_from_links:
        affiliate_networks = {**{k: 0 for k in networks_from_events}, **networks_from_links}
        attribution_source = "link_url"
    else:
        affiliate_networks = dict(networks_from_events)
        attribution_source = "none"

    affiliate_total = int(events.get("affiliate_click") or 0)
    attributed = sum(affiliate_networks.values())
    unattributed = max(affiliate_total - attributed, 0)

    yt_sessions = sum(
        int(float(row.get("sessions") or 0))
        for row in source_medium
        if "youtube" in (row.get("sessionSourceMedium") or "").lower()
    )

    return {
        "totals": totals,
        "top_pages": top_pages,
        "entry_channels": channels,
        "source_medium": source_medium,
        "events": events,
        "affiliate_networks": affiliate_networks,
        "affiliate_attribution_source": attribution_source,
        "affiliate_clicks_unattributed_7d": unattributed,
        "affiliate_links": link_rows,
        "affiliate_link_dimension": link_dim_used,
        "sessions_from_youtube": yt_sessions,
        "affiliate_clicks_7d": affiliate_total,
    }


def fetch_gsc(site_url: str) -> dict:
    token = google_token(["https://www.googleapis.com/auth/webmasters.readonly"])
    body = {
        "startDate": (datetime.now(timezone.utc).date()).isoformat(),  # overwritten below
        "endDate": datetime.now(timezone.utc).date().isoformat(),
        "dimensions": ["query"],
        "rowLimit": 15,
    }
    # last 7 days
    from datetime import timedelta

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=7)
    body["startDate"] = start.isoformat()
    body["endDate"] = end.isoformat()

    encoded = urllib.parse.quote(site_url, safe="")
    report = http_json(
        f"https://www.googleapis.com/webmasters/v3/sites/{encoded}/searchAnalytics/query",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
        body=body,
    )
    rows = []
    clicks = impressions = 0.0
    for row in report.get("rows") or []:
        c = float(row.get("clicks") or 0)
        im = float(row.get("impressions") or 0)
        clicks += c
        impressions += im
        keys = row.get("keys") or [""]
        rows.append(
            {
                "query": keys[0],
                "clicks": int(c),
                "impressions": int(im),
                "ctr": round(float(row.get("ctr") or 0) * 100, 2),
                "position": round(float(row.get("position") or 0), 1),
            }
        )
    return {
        "clicks": int(clicks),
        "impressions": int(impressions),
        "top_queries": rows,
        "site_url": site_url,
    }


def fetch_cloudflare(zone_id: str, token: str) -> dict:
    # Simple analytics via GraphQL httpRequests1dGroups last 7 days
    end = datetime.now(timezone.utc).date()
    from datetime import timedelta

    start = end - timedelta(days=7)
    query = {
        "query": """
        query ($zoneTag: string!, $since: Date!, $until: Date!) {
          viewer {
            zones(filter: { zoneTag: $zoneTag }) {
              httpRequests1dGroups(limit: 14, filter: { date_geq: $since, date_lt: $until }) {
                dimensions { date }
                sum { pageViews requests }
                uniq { uniques }
              }
            }
          }
        }
        """,
        "variables": {
            "zoneTag": zone_id,
            "since": start.isoformat(),
            "until": (end + timedelta(days=1)).isoformat(),
        },
    }
    # Cloudflare GraphQL variable types are finicky — use REST analytics if GraphQL fails
    try:
        data = http_json(
            "https://api.cloudflare.com/client/v4/graphql",
            method="POST",
            headers={"Authorization": f"Bearer {token}"},
            body=query,
        )
        zones = (((data.get("data") or {}).get("viewer") or {}).get("zones") or [])
        groups = (zones[0].get("httpRequests1dGroups") if zones else None) or []
        daily = []
        page_views = uniques = 0
        for g in groups:
            pv = int(((g.get("sum") or {}).get("pageViews")) or 0)
            uq = int(((g.get("uniq") or {}).get("uniques")) or 0)
            page_views += pv
            uniques += uq
            daily.append(
                {
                    "date": (g.get("dimensions") or {}).get("date"),
                    "page_views": pv,
                    "uniques": uq,
                }
            )
        daily.sort(key=lambda r: r.get("date") or "")
        return {
            "page_views": page_views,
            "uniques": uniques,
            "daily": daily,
            "note": "Cloudflare edge includes bots — prefer GA4 for human traffic",
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:240], "page_views": None, "uniques": None}


def fetch_youtube() -> dict:
    api_key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    if not api_key:
        return {"skipped": "Set YOUTUBE_API_KEY"}
    handle = (os.environ.get("YOUTUBE_CHANNEL_HANDLE") or "").strip().lstrip("@")
    channel_id = (os.environ.get("YOUTUBE_CHANNEL_ID") or "").strip()
    if not channel_id and YOUTUBE_ACCESS.is_file():
        try:
            access = json.loads(YOUTUBE_ACCESS.read_text(encoding="utf-8"))
            channel_id = str(((access.get("channel") or {}).get("id")) or "").strip()
        except json.JSONDecodeError:
            pass

    def yt_get(path: str, params: dict) -> dict:
        params = {**params, "key": api_key}
        url = f"https://www.googleapis.com/youtube/v3/{path}?{urllib.parse.urlencode(params)}"
        return http_json(url)

    if not channel_id:
        if not handle:
            return {"skipped": "Set YOUTUBE_CHANNEL_HANDLE or YOUTUBE_CHANNEL_ID"}
        data = yt_get("channels", {"part": "id,snippet,statistics", "forHandle": handle})
        items = data.get("items") or []
        if not items:
            return {"error": f"No channel for @{handle}"}
        channel_id = items[0]["id"]

    ch = yt_get("channels", {"part": "snippet,statistics,contentDetails", "id": channel_id})
    items = ch.get("items") or []
    if not items:
        return {"error": "Channel not found"}
    channel = items[0]
    stats = channel.get("statistics") or {}
    snippet = channel.get("snippet") or {}
    uploads = (channel.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
    videos: list[dict] = []
    if uploads:
        pl = yt_get("playlistItems", {"part": "contentDetails,snippet", "playlistId": uploads, "maxResults": "8"})
        ids = [
            it.get("contentDetails", {}).get("videoId")
            for it in (pl.get("items") or [])
            if it.get("contentDetails", {}).get("videoId")
        ]
        if ids:
            vd = yt_get("videos", {"part": "snippet,statistics", "id": ",".join(ids)})
            for v in vd.get("items") or []:
                st = v.get("statistics") or {}
                sn = v.get("snippet") or {}
                videos.append(
                    {
                        "id": v.get("id"),
                        "title": sn.get("title"),
                        "views": int(st.get("viewCount") or 0),
                        "likes": int(st.get("likeCount") or 0),
                        "published": sn.get("publishedAt"),
                        "url": f"https://www.youtube.com/watch?v={v.get('id')}",
                    }
                )
    return {
        "channel": {
            "id": channel_id,
            "title": snippet.get("title"),
            "handle": snippet.get("customUrl"),
            "subscribers": int(stats.get("subscriberCount") or 0),
            "views": int(stats.get("viewCount") or 0),
            "videos": int(stats.get("videoCount") or 0),
        },
        "recent_videos": videos,
    }


def load_amazon_manual() -> dict:
    if not AMAZON_MANUAL.is_file():
        return {
            "skipped": True,
            "configured": False,
            "note": "Paste Associates reports into products/analytics/amazon-manual.json",
            "clicks_7d": None,
            "ordered_items_7d": None,
            "earnings_7d_usd": None,
        }
    try:
        data = json.loads(AMAZON_MANUAL.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"error": str(exc), "skipped": True, "configured": False}

    updated = str(data.get("updated") or "").strip()
    has_numbers = any(
        data.get(key) is not None
        for key in ("clicks_7d", "ordered_items_7d", "earnings_7d_usd")
    )
    configured = bool(updated) and updated.upper() != "YYYY-MM-DD" and has_numbers
    data["configured"] = configured
    data["skipped"] = not configured
    if not configured:
        data["note"] = (
            data.get("notes")
            or "Manual Amazon report is still a placeholder — paste weekly Associates numbers."
        )
    return data


def affiliate_programs(ga4: dict, amazon: dict) -> list[dict]:
    networks = ga4.get("affiliate_networks") or {}
    amazon_configured = bool(amazon.get("configured"))
    click_grow = bool((os.environ.get("PUBLIC_CLICK_GROW_AFFILIATE_URL") or "").strip())
    gardeners = bool((os.environ.get("PUBLIC_GARDENERS_SUPPLY_AFFILIATE_URL") or "").strip())
    return [
        {
            "name": "Amazon Associates",
            "network": "amazon-associates",
            "status": "reporting" if amazon_configured else "active",
            "site_clicks_7d": networks.get("Amazon Associates", 0),
            "portal_clicks_7d": amazon.get("clicks_7d") if amazon_configured else None,
            "orders_7d": amazon.get("ordered_items_7d") if amazon_configured else None,
            "earnings_7d_usd": amazon.get("earnings_7d_usd") if amazon_configured else None,
            "next_step": (
                f"Manual report updated {amazon.get('updated')}."
                if amazon_configured
                else "Tagged links are live (sillgarden09-20). Paste weekly Associates numbers into amazon-manual.json."
            ),
        },
        {
            "name": "Click & Grow",
            "network": "click-grow",
            "status": "active" if click_grow else "applied",
            "site_clicks_7d": networks.get("Click & Grow", 0),
            "portal_clicks_7d": None,
            "orders_7d": None,
            "earnings_7d_usd": None,
            "next_step": (
                "Direct tracking URL configured."
                if click_grow
                else "Await approval, then set PUBLIC_CLICK_GROW_AFFILIATE_URL in GitHub and Cloudflare."
            ),
        },
        {
            "name": "Gardener's Supply",
            "network": "gardeners-supply",
            "status": "active" if gardeners else "not-applied",
            "site_clicks_7d": networks.get("Gardener's Supply", 0),
            "portal_clicks_7d": None,
            "orders_7d": None,
            "earnings_7d_usd": None,
            "next_step": (
                "Impact tracking URL configured."
                if gardeners
                else "Apply through Impact after Click & Grow; Amazon fallback remains live."
            ),
        },
    ]


def load_actions() -> list[dict]:
    if not ACTION_QUEUE.is_file():
        return []
    try:
        return (json.loads(ACTION_QUEUE.read_text(encoding="utf-8")).get("actions") or [])[:12]
    except json.JSONDecodeError:
        return []


def build_setup_checklist(sources: dict) -> list[dict]:
    checks = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    site = sources.get("site") or {}
    add("Site live", bool(site.get("ok")), SITE_URL)

    ga4 = sources.get("ga4") or {}
    add(
        "GA4 API",
        bool(ga4.get("totals")) and not ga4.get("error") and not ga4.get("skipped"),
        ga4.get("error") or ga4.get("skipped") or "Connected",
    )
    add(
        "GA4 client tag",
        bool((os.environ.get("PUBLIC_GA4_ID") or "").startswith("G-")),
        os.environ.get("PUBLIC_GA4_ID") or "Set PUBLIC_GA4_ID in .env + Cloudflare Pages",
    )

    gsc = sources.get("gsc") or {}
    add(
        "Search Console",
        bool(gsc.get("top_queries") is not None) and not gsc.get("error") and not gsc.get("skipped"),
        gsc.get("error") or gsc.get("skipped") or gsc.get("site_url") or "Connected",
    )

    cf = sources.get("cloudflare") or {}
    add(
        "Cloudflare analytics",
        cf.get("page_views") is not None and not cf.get("error") and not cf.get("skipped"),
        cf.get("error") or cf.get("skipped") or "Connected",
    )

    yt = sources.get("youtube") or {}
    add(
        "YouTube",
        bool((yt.get("channel") or {}).get("id")) and not yt.get("error") and not yt.get("skipped"),
        yt.get("error") or yt.get("skipped") or (yt.get("channel") or {}).get("title") or "Connected",
    )

    links = ga4.get("affiliate_links") or []
    link_ok = bool(ga4.get("affiliate_link_dimension")) or not any(
        isinstance(row, dict) and row.get("note") and "dimension" in str(row.get("note")).lower()
        for row in links
    )
    if ga4.get("error") or ga4.get("skipped"):
        link_ok = False
    add(
        "Affiliate click counters",
        bool(ga4.get("totals")) and link_ok and not ga4.get("error") and not ga4.get("skipped"),
        (
            ga4.get("error")
            or ga4.get("skipped")
            or (
                f"Per-link via {ga4.get('affiliate_link_dimension')}"
                if ga4.get("affiliate_link_dimension")
                else (links[0].get("note") if links and isinstance(links[0], dict) else "Network event counters ready")
            )
        ),
    )
    return checks


def append_history(snapshot: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    history: list = []
    if HISTORY.is_file():
        try:
            history = json.loads(HISTORY.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []
    hero = snapshot.get("hero") or {}
    history.append(
        {
            "generated_at": snapshot.get("generated_at"),
            "ga4_sessions_7d": hero.get("sessions_7d"),
            "ga4_pageviews_7d": hero.get("pageviews_7d"),
            "affiliate_clicks_7d": hero.get("affiliate_clicks_7d"),
            "gsc_clicks_7d": hero.get("gsc_clicks_7d"),
            "gsc_impressions_7d": hero.get("gsc_impressions_7d"),
            "cloudflare_page_views_7d": hero.get("cf_pageviews_7d"),
            "youtube_views_total": hero.get("youtube_views_total"),
            "amazon_earnings_7d_usd": hero.get("amazon_earnings_7d_usd"),
        }
    )
    HISTORY.write_text(json.dumps(history[-90:], indent=2), encoding="utf-8")


def main() -> int:
    load_dotenv()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sources: dict = {
        "site": probe_site(),
    }

    ga4_id = (os.environ.get("GA4_PROPERTY_ID") or "").strip()
    if ga4_id:
        try:
            sources["ga4"] = fetch_ga4(ga4_id)
        except Exception as exc:  # noqa: BLE001
            sources["ga4"] = {"error": str(exc)[:300], "skipped": False}
    else:
        sources["ga4"] = {"skipped": "Set GA4_PROPERTY_ID"}

    gsc_url = (os.environ.get("GSC_SITE_URL") or "sc-domain:sillgarden.com").strip()
    if os.environ.get("SKIP_GOOGLE_METRICS") == "1":
        sources["gsc"] = {"skipped": "SKIP_GOOGLE_METRICS=1"}
    else:
        try:
            sources["gsc"] = fetch_gsc(gsc_url)
        except Exception as exc:  # noqa: BLE001
            sources["gsc"] = {"error": str(exc)[:300], "skipped": False}

    cf_token = (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
    cf_zone = (os.environ.get("CLOUDFLARE_ZONE_ID") or "").strip()
    if cf_token and cf_zone:
        try:
            sources["cloudflare"] = fetch_cloudflare(cf_zone, cf_token)
        except Exception as exc:  # noqa: BLE001
            sources["cloudflare"] = {"error": str(exc)[:300]}
    else:
        sources["cloudflare"] = {"skipped": "Set CLOUDFLARE_API_TOKEN (+ ZONE_ID)"}

    try:
        sources["youtube"] = fetch_youtube()
    except Exception as exc:  # noqa: BLE001
        sources["youtube"] = {"error": str(exc)[:300]}

    sources["amazon"] = load_amazon_manual()

    ga4 = sources.get("ga4") or {}
    totals = ga4.get("totals") or {}
    gsc = sources.get("gsc") or {}
    cf = sources.get("cloudflare") or {}
    yt = sources.get("youtube") or {}
    amz = sources.get("amazon") or {}
    yt_ch = yt.get("channel") or {}

    hero = {
        "sessions_7d": totals.get("sessions"),
        "users_7d": totals.get("activeUsers"),
        "pageviews_7d": totals.get("screenPageViews"),
        "affiliate_clicks_7d": ga4.get("affiliate_clicks_7d"),
        "gsc_clicks_7d": gsc.get("clicks"),
        "gsc_impressions_7d": gsc.get("impressions"),
        "cf_pageviews_7d": cf.get("page_views"),
        "youtube_sessions_7d": ga4.get("sessions_from_youtube"),
        "youtube_subs": yt_ch.get("subscribers"),
        "youtube_views_total": yt_ch.get("views"),
        "amazon_clicks_7d": amz.get("clicks_7d"),
        "amazon_ordered_7d": amz.get("ordered_items_7d"),
        "amazon_earnings_7d_usd": amz.get("earnings_7d_usd"),
        "engagement_rate_pct": totals.get("engagementRate_pct"),
        "affiliate_ctr_pct": (
            round((ga4.get("affiliate_clicks_7d") or 0) / totals.get("sessions") * 100, 1)
            if totals.get("sessions")
            else 0
        ),
        "youtube_videos": yt_ch.get("videos"),
    }

    insights: list[str] = []
    if not (os.environ.get("PUBLIC_GA4_ID") or "").startswith("G-"):
        insights.append("Add PUBLIC_GA4_ID so the live site sends pageviews + affiliate_click events.")
    if ga4.get("skipped") or ga4.get("error"):
        insights.append("Connect GA4_PROPERTY_ID to unlock sessions / clicks on the dashboard.")
    if gsc.get("clicks") == 0 and not gsc.get("error"):
        insights.append("GSC shows 0 clicks — normal for a brand-new domain; submit sitemap in Search Console.")
    if (ga4.get("affiliate_clicks_7d") or 0) == 0 and totals.get("sessions"):
        insights.append("Traffic without affiliate clicks — check product CTAs and event firing.")
    if yt.get("skipped"):
        insights.append("Optional: set YOUTUBE_API_KEY + channel handle when you publish Sill Garden videos.")
    if amz.get("skipped"):
        insights.append("Amazon has no public API — paste weekly numbers into amazon-manual.json.")

    checklist = build_setup_checklist(sources)
    ready = sum(1 for c in checklist if c["ok"])

    snapshot = {
        "schema": "sill-garden-v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "site_url": SITE_URL,
        "amazon_tag": "sillgarden09-20",
        "hero": hero,
        "sources": sources,
        "monetization": {"affiliate_programs": affiliate_programs(ga4, amz)},
        "actions": load_actions(),
        "insights": insights,
        "setup": {"ready": ready, "total": len(checklist), "checks": checklist},
        "summary": {
            "headline": (
                f"Sessions {hero.get('sessions_7d') if hero.get('sessions_7d') is not None else '-'} | "
                f"Aff clicks {hero.get('affiliate_clicks_7d') if hero.get('affiliate_clicks_7d') is not None else '-'} | "
                f"GSC {hero.get('gsc_clicks_7d') if hero.get('gsc_clicks_7d') is not None else '-'} | "
                f"Setup {ready}/{len(checklist)}"
            )
        },
    }

    LATEST.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    append_history(snapshot)
    print(json.dumps({"ok": True, "path": str(LATEST), "headline": snapshot["summary"]["headline"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
