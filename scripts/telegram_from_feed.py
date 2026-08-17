#!/usr/bin/env python3
"""Post the newest unposted Sill Garden RSS item to Telegram."""

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
STATE_PATH = ROOT / "products" / "syndication" / "telegram-state.json"
COOLDOWN_DAYS = 3


def last_post_date(state: dict) -> date | None:
    try:
        return date.fromisoformat(str(state.get("lastPostAt") or ""))
    except ValueError:
        return None


def send_message(bot_token: str, chat_id: str, text: str) -> dict:
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": "false",
            }
        ).encode(),
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SillGarden/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
            message = (data.get("result") or {}) if data.get("ok") else {}
            return {
                "ok": bool(data.get("ok")),
                "message_id": message.get("message_id"),
                "status": response.status,
            }
    except urllib.error.HTTPError as exc:
        return {
            "error": exc.read().decode("utf-8", errors="replace")[:400],
            "status": exc.code,
        }
    except urllib.error.URLError as exc:
        return {"error": str(exc.reason)}


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Broadcast Sill Garden RSS to Telegram")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignore the 3-day cooldown")
    parser.add_argument("--feed", default=DEFAULT_FEED_URL)
    args = parser.parse_args()
    dry_run = args.dry_run or not automation_live()

    state = load_state(STATE_PATH)
    last = last_post_date(state)
    if not args.force and last and date.today() - last < timedelta(days=COOLDOWN_DAYS):
        print(f"Telegram: cooldown ({COOLDOWN_DAYS} days); last post was {last}.")
        return 0
    try:
        item = pick_new_item(
            fetch_rss_items(args.feed), set(state.get("posted_guids") or [])
        )
    except Exception as exc:
        print(f"Telegram: feed unavailable — skip ({exc}).", file=sys.stderr)
        return 0
    if not item:
        print("Telegram: no new feed items.")
        return 0

    text = f"{item['title']}\n\n{item['link']}"
    if dry_run:
        print(f"DRY RUN — Telegram would post:\n{text}")
        return 0

    bot_token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHANNEL_ID") or "").strip()
    if not bot_token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID — skip.", file=sys.stderr)
        return 0

    result = send_message(bot_token, chat_id, text)
    print(f"Telegram: {json.dumps(result, ensure_ascii=False)}")
    if result.get("ok"):
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
