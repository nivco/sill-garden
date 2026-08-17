#!/usr/bin/env python3
"""Request best-effort Wayback captures for Sill Garden's key pages."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_dotenv

BASE_URL = "https://sillgarden.com"
URLS = [
    f"{BASE_URL}/",
    f"{BASE_URL}/guides/",
    f"{BASE_URL}/guides/aerogarden-vs-click-and-grow/",
    f"{BASE_URL}/guides/best-countertop-garden-apartments/",
    f"{BASE_URL}/guides/best-low-light-herbs-apartment/",
    f"{BASE_URL}/feed.xml",
]


def archive_auth() -> str | None:
    key = (
        os.environ.get("IA_ACCESS_KEY")
        or os.environ.get("SAVEPAGENOW_ACCESS_KEY")
        or ""
    ).strip()
    secret = (
        os.environ.get("IA_SECRET_KEY")
        or os.environ.get("SAVEPAGENOW_SECRET_KEY")
        or ""
    ).strip()
    return f"LOW {key}:{secret}" if key and secret else None


def save_page(url: str, auth: str | None) -> tuple[int, str]:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "SillGarden/1.0 (+https://sillgarden.com; archive)",
    }
    if auth:
        headers["Authorization"] = auth
    request = urllib.request.Request(
        "https://web.archive.org/save",
        data=urllib.parse.urlencode(
            {
                "url": url,
                "capture_all": "1",
                "skip_first_archive": "1",
                "delay_wb_availability": "1",
            }
        ).encode(),
        method="POST",
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        location = response.headers.get("Content-Location", "") or ""
        if location.startswith("/web/"):
            location = "https://web.archive.org" + location
        return int(response.status), location


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Save key Sill Garden pages to Wayback")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    auth = archive_auth()
    if auth:
        print("Wayback: authenticated saves enabled.")

    successes = 0
    for url in URLS:
        if args.dry_run:
            print(f"DRY RUN — Wayback would save {url}")
            continue
        try:
            status, snapshot = save_page(url, auth)
            successes += int(status < 400)
            print(f"Wayback: {status} {url}" + (f" -> {snapshot}" if snapshot else ""))
        except Exception as exc:
            print(f"Wayback save failed: {url} ({exc})", file=sys.stderr)
    if not args.dry_run and not successes:
        print("Wayback: no captures succeeded (non-fatal).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
