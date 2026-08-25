#!/usr/bin/env python3
"""Lightweight traffic actions from analytics (Sill Garden).

  python scripts/traffic_optimizer.py
  python scripts/traffic_optimizer.py --refresh
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "products" / "analytics" / "latest.json"
OUT_DIR = ROOT / "products" / "traffic"
QUEUE = OUT_DIR / "action-queue.json"
STATE = OUT_DIR / "optimizer-state.json"
INDEXING_STATUS = ROOT / "products" / "analytics" / "indexing-status.json"
MIN_HOURS_INDEXNOW = 20


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def task(priority: str, category: str, title: str, detail: str, *, auto: bool = False, done: bool = False) -> dict:
    return {
        "priority": priority,
        "category": category,
        "title": title,
        "detail": detail,
        "auto": auto,
        "done": done,
        "created": now_utc(),
    }


def hours_since(iso_or_display: str | None) -> float | None:
    if not iso_or_display:
        return None
    raw = iso_or_display.replace(" UTC", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except ValueError:
        return None


def build_queue(data: dict, state: dict) -> tuple[list[dict], dict, list[str]]:
    actions: list[dict] = []
    applied: list[str] = []
    hero = data.get("hero") or {}
    sources = data.get("sources") or {}
    gsc = sources.get("gsc") or {}
    ga4 = sources.get("ga4") or {}
    setup = data.get("setup") or {}

    ga4_error = str((ga4.get("error") or "")).strip()
    gsc_error = str((gsc.get("error") or "")).strip()
    oauth_broken = bool(ga4_error or gsc_error) and (
        "invalid_grant" in (ga4_error + gsc_error).lower()
        or "invalid_scope" in (ga4_error + gsc_error).lower()
        or "token" in (ga4_error + gsc_error).lower()
    )

    sessions_raw = hero.get("sessions_7d")
    sessions = int(sessions_raw or 0) if sessions_raw is not None else None
    aff = hero.get("affiliate_clicks_7d") or 0
    gsc_clicks = hero.get("gsc_clicks_7d") or 0
    gsc_impr = hero.get("gsc_impressions_7d") or 0

    # OAuth/measurement first — never treat a failed pull as "no traffic".
    if oauth_broken or ga4_error or gsc_error:
        detail = ga4_error or gsc_error
        actions.append(
            task(
                "P0",
                "setup",
                "Re-auth Google OAuth (GA4/GSC)",
                "Token expired/revoked or scope broken. "
                "From Maker Tool Stack: python scripts/google_oauth_login.py --force "
                "then python scripts/google_token_sync.py. "
                f"Detail: {detail[:180]}",
            )
        )
    elif sessions == 0:
        actions.append(
            task(
                "P0",
                "acquisition",
                "No GA4 sessions yet",
                "Share 1–2 guides or request indexing on home + top guides in Search Console.",
            )
        )
    indexing = load_json(INDEXING_STATUS, {})
    indexed = int(indexing.get("indexed_count") or 0)
    sitemap_total = int(indexing.get("sitemap_url_count") or 0)
    missing = indexing.get("not_indexed_urls") or []

    # One indexing action covering all missing guides (not one row each).
    missing_guides: list[str] = []
    for row in missing:
        url = str(row.get("url") or "")
        if "/guides/" not in url or url.rstrip("/").endswith("/guides"):
            continue
        missing_guides.append(url.rstrip("/").split("/")[-1])
    if missing_guides:
        actions.append(
            task(
                "P1",
                "indexing",
                f"Request indexing for {len(missing_guides)} guides",
                "Search Console → URL Inspection → Request indexing once each: "
                + ", ".join(missing_guides)
                + ".",
            )
        )

    climb_bits: list[str] = []
    for q in (gsc.get("top_queries") or [])[:15]:
        pos = q.get("position")
        clicks = q.get("clicks") or 0
        impr = q.get("impressions") or 0
        query = q.get("query") or ""
        if not query or pos is None:
            continue
        pos_f = float(pos)
        if clicks > 0:
            continue
        if 4 <= pos_f <= 20 and impr >= 10:
            climb_bits.append(f"“{query}” pos {pos_f:.0f}/{impr} impr (CTR)")
        elif pos_f > 20 and impr >= 1:
            climb_bits.append(f"“{query}” pos {pos_f:.0f}/{impr} impr")

    if gsc_impr == 0 and not gsc.get("error"):
        if indexed:
            actions.append(
                task(
                    "P2",
                    "seo",
                    "Indexed pages have no search impressions yet",
                    f"Google inspection confirms {indexed}/{sitemap_total} URLs indexed. "
                    "No crawl fix is needed; allow ranking time and strengthen topic coverage.",
                )
            )
        else:
            actions.append(
                task(
                    "P1",
                    "indexing",
                    "Verify Google index coverage",
                    "Run python scripts/check_indexing.py; zero impressions alone does not mean pages are unindexed.",
                )
            )
    elif climb_bits:
        actions.append(
            task(
                "P1",
                "seo",
                "Climb ranking on early GSC queries",
                "Already showing for: "
                + "; ".join(climb_bits[:4])
                + ". Keep the matching guide title/FAQ tight; promote via YouTube — don't spam re-index.",
            )
        )
    elif gsc_impr > 0 and gsc_clicks == 0 and not gsc.get("error"):
        actions.append(
            task(
                "P2",
                "seo",
                "Search impressions without clicks yet",
                f"{gsc_impr} impressions / 0 clicks in 7d — wait for ranking or tighten the comparison guide.",
            )
        )

    # Only nudge content refresh when a guide has real traffic but no affiliate clicks sitewide.
    if sessions is not None and sessions >= 20 and aff == 0:
        top_guide = None
        for page in (ga4.get("top_pages") or [])[:8]:
            path = str(page.get("pagePath") or page.get("path") or "")
            if "/guides/" in path and path.rstrip("/") != "/guides":
                top_guide = path.rstrip("/").split("/")[-1]
                break
        if top_guide:
            actions.append(
                task(
                    "P2",
                    "content",
                    f"Check CTAs on {top_guide}",
                    "Sessions without affiliate clicks — confirm product cards and affiliate_click events.",
                )
            )

    # Skip per-check setup spam when we already raised a single OAuth P0.
    if not oauth_broken:
        ready = (setup.get("ready") or 0), (setup.get("total") or 7)
        if ready[0] < ready[1]:
            for c in setup.get("checks") or []:
                if not c.get("ok"):
                    name = str(c.get("name") or "setup")
                    detail = str(c.get("detail") or "")[:200]
                    # Collapse GA4/GSC/affiliate failures that are the same auth error.
                    if any(tok in detail.lower() for tok in ("invalid_grant", "invalid_scope", "token")):
                        continue
                    actions.append(task("P2", "setup", f"Finish setup: {name}", detail))

    if sessions is not None and sessions > 0 and aff == 0:
        actions.append(
            task(
                "P1",
                "monetization",
                "Traffic without affiliate clicks",
                "Confirm Amazon CTAs fire affiliate_click and links use sillgarden09-20.",
            )
        )

    # Throttled IndexNow (auto)
    hrs = hours_since(state.get("lastIndexNowAt"))
    if hrs is None or hrs >= MIN_HOURS_INDEXNOW:
        try:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "submit_indexing.py")],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if proc.returncode == 0 and "IndexNow OK" in (proc.stdout + proc.stderr):
                state["lastIndexNowAt"] = now_utc()
                applied.append("IndexNow ping")
                actions.append(
                    task("P3", "indexing", "IndexNow ping", "Re-notified Bing/Yandex of sitemap URLs.", auto=True, done=True)
                )
            else:
                actions.append(
                    task(
                        "P3",
                        "indexing",
                        "IndexNow ping skipped/failed",
                        ((proc.stdout or "") + (proc.stderr or ""))[:240],
                        auto=True,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            actions.append(task("P3", "indexing", "IndexNow error", str(exc)[:200], auto=True))
    else:
        actions.append(
            task(
                "P3",
                "indexing",
                "IndexNow throttled",
                f"Last ping {state.get('lastIndexNowAt')} ({hrs:.1f}h ago; min {MIN_HOURS_INDEXNOW}h).",
                auto=True,
                done=True,
            )
        )

    # Deduplicate by title
    seen: set[str] = set()
    unique: list[dict] = []
    for a in actions:
        if a["title"] in seen:
            continue
        seen.add(a["title"])
        unique.append(a)

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    unique.sort(key=lambda a: priority_order.get(a["priority"], 9))
    state["runs"] = int(state.get("runs") or 0) + 1
    state["lastRunAt"] = now_utc()
    return unique[:25], state, applied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Run analytics_summary first")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "scripts"))
    from analytics_summary import load_dotenv
    from measurement_gate import require_google_access

    load_dotenv()

    if args.refresh:
        from analytics_summary import main as summary_main

        summary_main()

    gate = require_google_access(strict=False, warn_only=True)
    data = load_json(LATEST, {})
    if not data:
        print("No latest.json — run analytics_summary.py first", file=sys.stderr)
        return 1

    state = load_json(STATE, {"lastIndexNowAt": None, "runs": 0})
    queue, state, applied = build_queue(data, state)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": now_utc(),
        "site_url": "https://sillgarden.com",
        "gate_ok": gate == 0,
        "applied": applied,
        "actions": queue,
    }
    QUEUE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "actions": len(queue), "applied": applied}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
