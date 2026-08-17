#!/usr/bin/env python3
"""Post the newest unposted Sill Garden RSS item to Mastodon."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import automation_live, load_dotenv
from feed_broadcast import DEFAULT_FEED_URL, fetch_rss_items, load_state, pick_new_item, save_state

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "products" / "syndication" / "mastodon-state.json"
COOLDOWN_DAYS = 3


def last_post_date(state: dict) -> date | None:
    try:
        return date.fromisoformat(str(state.get("lastPostAt") or ""))
    except ValueError:
        return None


def post_status(instance: str, token: str, text: str) -> dict:
    request = urllib.request.Request(
        f"{instance.rstrip('/')}/api/v1/statuses",
        data=urllib.parse.urlencode({"status": text, "visibility": "public"}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SillGarden/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
            return {"id": data.get("id"), "url": data.get("url"), "status": response.status}
    except urllib.error.HTTPError as exc:
        return {
            "error": exc.read().decode("utf-8", errors="replace")[:400],
            "status": exc.code,
        }
    except urllib.error.URLError as exc:
        return {"error": str(exc.reason)}


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Broadcast Sill Garden RSS to Mastodon")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignore the 3-day cooldown")
    parser.add_argument("--feed", default=DEFAULT_FEED_URL)
    args = parser.parse_args()
    dry_run = args.dry_run or not automation_live()

    state = load_state(STATE_PATH)
    last = last_post_date(state)
    if not args.force and last and date.today() - last < timedelta(days=COOLDOWN_DAYS):
        print(f"Mastodon: cooldown ({COOLDOWN_DAYS} days); last post was {last}.")
        return 0

    try:
        item = pick_new_item(
            fetch_rss_items(args.feed), set(state.get("posted_guids") or [])
        )
    except Exception as exc:  # network/XML failures should not break the workflow
        print(f"Mastodon: feed unavailable — skip ({exc}).", file=sys.stderr)
        return 0
    if not item:
        print("Mastodon: no new feed items.")
        return 0

    text = (
        f"{item['title']}\n\n{item['link']}\n\n"
        "#IndoorGarden #ApartmentLiving #Herbs"
    )
    if dry_run:
        print(f"DRY RUN — Mastodon would post:\n{text}")
        return 0

    instance = (os.environ.get("MASTODON_INSTANCE") or "").strip()
    token = (os.environ.get("MASTODON_ACCESS_TOKEN") or "").strip()
    if not instance or not token:
        print("Missing MASTODON_INSTANCE or MASTODON_ACCESS_TOKEN — skip.", file=sys.stderr)
        return 0

    result = post_status(instance, token, text)
    print(f"Mastodon: {json.dumps(result, ensure_ascii=False)}")
    if result.get("id"):
        posted = set(state.get("posted_guids") or [])
        posted.add(item["guid"])
        state["posted_guids"] = sorted(posted)[-80:]
        state.setdefault("posts", []).append(
            {"date": date.today().isoformat(), "guid": item["guid"], "link": item["link"], **result}
        )
        state["posts"] = state["posts"][-80:]
        state["lastPostAt"] = date.today().isoformat()
        save_state(STATE_PATH, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
