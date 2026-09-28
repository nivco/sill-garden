#!/usr/bin/env python3
"""Post the newest unposted Sill Garden feed item to Bluesky."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import automation_live, load_dotenv
from bluesky_common import api, login, post_record
from feed_broadcast import DEFAULT_FEED_URL, fetch_rss_items, load_state, pick_new_item, save_state

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "products" / "syndication" / "bluesky-state.json"
COOLDOWN_DAYS = 3


def last_post_date(state: dict) -> date | None:
    try:
        return date.fromisoformat(str(state.get("lastPostAt") or ""))
    except ValueError:
        return None


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Broadcast Sill Garden RSS to Bluesky")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignore the 3-day cooldown")
    parser.add_argument("--feed", default=DEFAULT_FEED_URL)
    args = parser.parse_args()
    dry_run = args.dry_run or not automation_live()

    state = load_state(STATE_PATH)
    last = last_post_date(state)
    if not args.force and last and date.today() - last < timedelta(days=COOLDOWN_DAYS):
        print(f"Bluesky: cooldown ({COOLDOWN_DAYS} days); last post was {last}.")
        return 0

    try:
        item = pick_new_item(
            fetch_rss_items(args.feed), set(state.get("posted_guids") or [])
        )
    except Exception as exc:
        print(f"Bluesky: feed unavailable — {exc}", file=sys.stderr)
        item = None

    # MTS-style fallback: post today's distribution pack when RSS has nothing new.
    if not item:
        dist_path = ROOT / "products" / "growth" / "distribution" / "latest.json"
        if dist_path.is_file():
            try:
                pack = json.loads(dist_path.read_text(encoding="utf-8"))
                text_dist = ((pack.get("channels") or {}).get("bluesky") or "").strip()
                url = ((pack.get("target") or {}).get("url") or "").strip()
                if text_dist:
                    item = {
                        "guid": f"dist:{url or date.today().isoformat()}",
                        "title": text_dist.split("\n", 1)[0][:120],
                        "link": url or "https://sillgarden.com/",
                        "dist_text": text_dist,
                    }
            except (json.JSONDecodeError, OSError):
                item = None
    if not item:
        print("Bluesky: no new feed items and no distribution pack.")
        return 0

    if item.get("dist_text"):
        text = item["dist_text"]
        if len(text) > 300:
            text = text[:297].rstrip() + "..."
    else:
        suffix = "\n\n#IndoorGarden #ApartmentLiving"
        available = 300 - len(item["link"]) - len(suffix) - 2
        title = item["title"]
        if len(title) > available:
            title = title[: max(1, available - 1)].rstrip() + "..."
        text = f"{title}\n\n{item['link']}{suffix}"
    if dry_run:
        print(f"DRY RUN — Bluesky would post:\n{text}")
        return 0

    identifier = (os.environ.get("BLUESKY_IDENTIFIER") or "").strip()
    password = (os.environ.get("BLUESKY_APP_PASSWORD") or "").strip()
    if not identifier or not password:
        print("Missing BLUESKY_IDENTIFIER or BLUESKY_APP_PASSWORD — skip.", file=sys.stderr)
        return 0

    try:
        session = login(identifier, password)
        result = api(
            "POST",
            "/com.atproto.repo.createRecord",
            session["accessJwt"],
            {
                "repo": session["did"],
                "collection": "app.bsky.feed.post",
                "record": post_record(text),
            },
        )
    except (KeyError, RuntimeError) as exc:
        print(f"Bluesky post failed: {exc}", file=sys.stderr)
        return 0

    posted = set(state.get("posted_guids") or [])
    posted.add(item["guid"])
    state["posted_guids"] = sorted(posted)[-80:]
    state.setdefault("posts", []).append(
        {
            "date": date.today().isoformat(),
            "guid": item["guid"],
            "link": item.get("link"),
            "uri": result.get("uri"),
            "cid": result.get("cid"),
        }
    )
    state["posts"] = state["posts"][-80:]
    state["lastPostAt"] = date.today().isoformat()
    save_state(STATE_PATH, state)
    print(f"Bluesky: posted {json.dumps(result, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
