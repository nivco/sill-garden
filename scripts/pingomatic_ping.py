#!/usr/bin/env python3
"""Notify Ping-o-Matic about the Sill Garden RSS feed."""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request

FEED_URL = "https://sillgarden.com/feed.xml"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ping Sill Garden's RSS update")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    params = urllib.parse.urlencode(
        {
            "title": "Sill Garden",
            "blogurl": "https://sillgarden.com/",
            "rssurl": FEED_URL,
        }
    )
    url = f"https://pingomatic.com/ping/?{params}"
    if args.dry_run:
        print(f"DRY RUN — GET {url}")
        return 0
    request = urllib.request.Request(
        url, headers={"User-Agent": "SillGarden/1.0"}, method="GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(f"Ping-o-Matic: {response.status}")
    except Exception as exc:
        print(f"Ping-o-Matic failed (non-fatal): {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
