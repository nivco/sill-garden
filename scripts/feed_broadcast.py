#!/usr/bin/env python3
"""Shared RSS and state helpers for Sill Garden distribution scripts."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_FEED_URL = "https://sillgarden.com/feed.xml"
USER_AGENT = "SillGarden/1.0 (+https://sillgarden.com)"


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", unescape(text or "")).strip()


def _published_timestamp(value: str) -> float:
    if not value:
        return 0
    try:
        return parsedate_to_datetime(value).timestamp()
    except (TypeError, ValueError, OverflowError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0


def fetch_rss_items(feed_url: str = DEFAULT_FEED_URL, *, limit: int = 30) -> list[dict]:
    req = Request(feed_url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as response:
        raw = response.read()
    if b"<rss" not in raw[:1000].lower():
        raise ValueError(f"{feed_url} did not return an RSS document")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"{feed_url} returned malformed RSS: {exc}") from exc

    channel = root.find("channel")
    if channel is None:
        return []

    items: list[dict] = []
    for item in channel.findall("item"):
        title = strip_html(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link or title).strip()
        published = (item.findtext("pubDate") or "").strip()
        description = strip_html(item.findtext("description") or "")
        if title and link:
            items.append(
                {
                    "guid": guid,
                    "title": title,
                    "link": link,
                    "pubDate": published,
                    "description": description,
                }
            )

    items.sort(key=lambda entry: _published_timestamp(entry["pubDate"]), reverse=True)
    return items[: max(0, limit)]


def load_state(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"posted_guids": [], "posts": []}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pick_new_item(items: list[dict], posted: set[str]) -> dict | None:
    return next((item for item in items if item["guid"] not in posted), None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview the Sill Garden RSS feed")
    parser.add_argument("--feed", default=DEFAULT_FEED_URL)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    try:
        items = fetch_rss_items(args.feed, limit=args.limit)
    except Exception as exc:
        print(f"Feed unavailable — skip ({exc}).")
        return 0
    for item in items:
        print(f"{item['pubDate']}  {item['title']}\n  {item['link']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
