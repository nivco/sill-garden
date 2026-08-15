#!/usr/bin/env python3
"""Inspect sitemap and Google indexing state for Sill Garden priority URLs."""

from __future__ import annotations

import json
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytics_summary import google_token, http_json, load_dotenv
from submit_indexing import sitemap_urls

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "products" / "analytics" / "indexing-status.json"
SITE = "sc-domain:sillgarden.com"
SITEMAP = "https://sillgarden.com/sitemap-index.xml"
SCOPE = ["https://www.googleapis.com/auth/webmasters.readonly"]


def inspect_url(token: str, url: str) -> dict:
    response = http_json(
        "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
        body={"inspectionUrl": url, "siteUrl": SITE, "languageCode": "en-US"},
    )
    result = (response.get("inspectionResult") or {}).get("indexStatusResult") or {}
    return {
        "url": url,
        "verdict": result.get("verdict"),
        "coverage_state": result.get("coverageState"),
        "indexing_state": result.get("indexingState"),
        "robots_txt_state": result.get("robotsTxtState"),
        "page_fetch_state": result.get("pageFetchState"),
        "last_crawl_time": result.get("lastCrawlTime"),
        "google_canonical": result.get("googleCanonical"),
        "user_canonical": result.get("userCanonical"),
        "referring_urls": result.get("referringUrls") or [],
    }


def sitemap_status(token: str) -> dict:
    site = urllib.parse.quote(SITE, safe="")
    feed = urllib.parse.quote(SITEMAP, safe="")
    try:
        response = http_json(
            f"https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{feed}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return {
            "path": response.get("path"),
            "last_submitted": response.get("lastSubmitted"),
            "is_pending": response.get("isPending"),
            "is_sitemaps_index": response.get("isSitemapsIndex"),
            "last_downloaded": response.get("lastDownloaded"),
            "warnings": response.get("warnings"),
            "errors": response.get("errors"),
            "contents": response.get("contents") or [],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:500]}


def main() -> int:
    load_dotenv()
    token = google_token(SCOPE)
    urls = sitemap_urls()
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
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
