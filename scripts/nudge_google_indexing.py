#!/usr/bin/env python3
"""Nudge Google/Bing toward crawl+index for priority Sill Garden URLs.

Google does not expose the Search Console "Request indexing" button via API for
ordinary web pages. This script does the closest automatable steps:

1. Resubmit the sitemap in Search Console (needs webmasters write scope)
2. Ping IndexNow for priority / unknown URLs (Bing/Yandex)
3. Re-run URL Inspection and refresh products/analytics/indexing-status.json
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytics_summary import google_token, http_json, load_dotenv
from check_indexing import inspect_url, sitemap_status
from submit_indexing import ping_indexnow, sitemap_urls

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "products" / "analytics" / "indexing-status.json"
SITE = "sc-domain:sillgarden.com"
SITEMAP = "https://sillgarden.com/sitemap-index.xml"

PRIORITY = [
    "https://sillgarden.com/",
    "https://sillgarden.com/about/",
    "https://sillgarden.com/tools/",
    "https://sillgarden.com/tools/kit-picker/",
    "https://sillgarden.com/tools/apartment-herb-checklist/",
    "https://sillgarden.com/guides/aerogarden-vs-click-and-grow/",
    "https://sillgarden.com/guides/compare-aerogarden-models/",
    "https://sillgarden.com/guides/best-countertop-garden-apartments/",
    "https://sillgarden.com/guides/cheapest-indoor-herb-garden-apartment/",
    "https://sillgarden.com/guides/kratky-jar-herbs-apartment/",
    "https://sillgarden.com/guides/yellow-leaves-leggy-seedlings-indoor-herbs/",
]


def submit_sitemap(token: str) -> dict:
    site = urllib.parse.quote(SITE, safe="")
    feed = urllib.parse.quote(SITEMAP, safe="")
    url = f"https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{feed}"
    req = urllib.request.Request(
        url,
        data=b"",
        method="PUT",
        headers={"Authorization": f"Bearer {token}", "Content-Length": "0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return {"ok": True, "status": resp.status}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        return {"ok": False, "status": exc.code, "detail": detail}


def main() -> int:
    load_dotenv()
    import os

    report: dict = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "GSC UI 'Request indexing' cannot be called via API for normal pages. "
            "This run resubmits the sitemap, IndexNow-pings priority URLs, and refreshes inspection."
        ),
        "priority": PRIORITY,
    }

    # Prefer write scope for sitemap PUT; fall back to readonly for inspection.
    write_scope = ["https://www.googleapis.com/auth/webmasters"]
    read_scope = ["https://www.googleapis.com/auth/webmasters.readonly"]
    token = None
    try:
        token = google_token(write_scope)
        report["gsc_scope"] = "webmasters"
    except Exception as exc:  # noqa: BLE001
        report["gsc_write_error"] = str(exc)[:300]
        token = google_token(read_scope)
        report["gsc_scope"] = "webmasters.readonly"

    report["sitemap_submit"] = submit_sitemap(token)
    if not report["sitemap_submit"].get("ok"):
        print(f"Sitemap submit: {report['sitemap_submit']}", file=sys.stderr)
    else:
        print("Sitemap resubmitted to Search Console")

    urls = list(dict.fromkeys([*PRIORITY, *sitemap_urls()]))
    key = (os.environ.get("INDEXNOW_KEY") or "").strip()
    if key:
        try:
            ping_indexnow(urls, key)
            report["indexnow"] = {"ok": True, "count": len(urls)}
        except Exception as exc:  # noqa: BLE001
            report["indexnow"] = {"ok": False, "error": str(exc)[:300]}
            print(f"IndexNow failed: {exc}", file=sys.stderr)
    else:
        report["indexnow"] = {"ok": False, "error": "INDEXNOW_KEY missing"}
        print("INDEXNOW_KEY missing — skip IndexNow", file=sys.stderr)

    results: list[dict] = []
    for url in urls:
        try:
            results.append(inspect_url(token, url))
        except Exception as exc:  # noqa: BLE001
            results.append({"url": url, "error": str(exc)[:500]})

    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "site": SITE,
        "sitemap": sitemap_status(token),
        "sitemap_url_count": len(urls),
        "urls": results,
        "nudge": report,
    }
    payload["indexed_count"] = sum(
        1
        for row in results
        if row.get("verdict") == "PASS" and "indexed" in (row.get("coverage_state") or "").lower()
    )
    payload["not_indexed_count"] = max(len(results) - payload["indexed_count"], 0)
    payload["not_indexed_urls"] = [
        {
            "url": row.get("url"),
            "coverage_state": row.get("coverage_state") or row.get("error") or "Unknown",
        }
        for row in results
        if row.get("verdict") != "PASS" or "indexed" not in (row.get("coverage_state") or "").lower()
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"nudge": report, "indexed": payload["indexed_count"], "not_indexed": payload["not_indexed_urls"]}, indent=2))
    print(
        "Reminder: for still-unknown URLs, use Search Console → URL Inspection → Request indexing "
        "(Google blocks that action from the API)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
