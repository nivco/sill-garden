#!/usr/bin/env python3
"""Publish the Sill Garden RSS URL to common WebSub hubs."""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request

FEED_URL = "https://sillgarden.com/feed.xml"
HUBS = [
    "https://pubsubhubbub.appspot.com/",
    "https://superfeedr.com/hubbub",
]


def publish(hub: str) -> int:
    request = urllib.request.Request(
        hub,
        data=urllib.parse.urlencode(
            {"hub.mode": "publish", "hub.url": FEED_URL}
        ).encode(),
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SillGarden/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return int(response.status)


def main() -> int:
    parser = argparse.ArgumentParser(description="Notify WebSub hubs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for hub in HUBS:
        if args.dry_run:
            print(f"DRY RUN — publish {FEED_URL} to {hub}")
            continue
        try:
            print(f"WebSub: {publish(hub)} {hub}")
        except Exception as exc:
            print(f"WebSub failed (non-fatal): {hub} ({exc})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
