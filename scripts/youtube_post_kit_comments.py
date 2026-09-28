#!/usr/bin/env python3
"""Post kit-link channel comments on top Sill Garden Shorts.

YouTube Data API cannot pin comments. This posts as the channel (visible as a
creator comment). Pin in Studio if you want it sticky — paste is already live.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_access_gate import check
from youtube_common import kit_comment_text, load_json, load_publish_state, save_publish_state
from youtube_upload import service

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "products" / "analytics" / "latest.json"

# Prefer Shorts that already have traction, then money-topic Shorts.
PRIORITY_IDS = [
    "CTmzbmQ5FAw",  # Bounty vs Harvest Short (~28 views)
    "F073SleZ9aA",  # Kratky Short
    "NSLsa1eJxko",  # AeroGarden vs Click & Grow Short
    "tGr1dpUCGXo",  # best countertop Short
    "s7KtScEHU6o",  # cheapest Short (if present)
]


def automation_live() -> bool:
    return (os.environ.get("AUTOMATION_LIVE") or "").strip().lower() in {"1", "true", "yes"}


def views_by_id() -> dict[str, int]:
    data = load_json(ANALYTICS, {})
    out: dict[str, int] = {}
    recent = ((data.get("sources") or {}).get("youtube") or {}).get("recent_videos") or []
    for item in recent:
        vid = str(item.get("id") or "").strip()
        if vid:
            out[vid] = int(item.get("views") or 0)
    return out


def short_targets(limit: int) -> list[tuple[str, dict]]:
    state = load_publish_state()
    uploads = state.get("uploads") or {}
    views = views_by_id()
    shorts: list[tuple[str, dict, int, int]] = []
    for key, item in uploads.items():
        if str(item.get("format") or "").lower() != "short":
            continue
        yt_id = str(item.get("youtube_id") or "").strip()
        if not yt_id:
            continue
        try:
            pri = PRIORITY_IDS.index(yt_id)
        except ValueError:
            pri = 100 + len(PRIORITY_IDS)
        shorts.append((key, item, pri, -views.get(yt_id, 0)))
    shorts.sort(key=lambda row: (row[2], row[3], row[0]))
    return [(key, item) for key, item, _, _ in shorts[:limit]]


def already_commented(item: dict) -> bool:
    return bool(str(item.get("kit_comment_id") or "").strip())


def post_comment(youtube, video_id: str, text: str) -> str:
    body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {"snippet": {"textOriginal": text}},
        }
    }
    resp = youtube.commentThreads().insert(part="snippet", body=body).execute()
    return str((((resp.get("snippet") or {}).get("topLevelComment") or {}).get("id")) or resp.get("id") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=8, help="Max Shorts to comment on")
    args = parser.parse_args()

    targets = short_targets(args.limit)
    if not targets:
        print("No Shorts with youtube_id found.")
        return 0

    text = kit_comment_text()
    if args.dry_run:
        for key, item in targets:
            status = "skip (already posted)" if already_commented(item) else "would post"
            print(f"DRY RUN [{status}]: {key} {item.get('youtube_id')} {item.get('url')}")
            print(text)
            print()
        return 0

    if not automation_live():
        print("Refusing YouTube mutation: set AUTOMATION_LIVE=1 or use --dry-run.", file=sys.stderr)
        return 1

    gate = check()
    if not gate.get("ready"):
        print(gate.get("error") or "YouTube access gate failed", file=sys.stderr)
        return 1

    youtube = service()
    state = load_publish_state()
    uploads = state.get("uploads") or {}
    posted = 0
    skipped = 0
    for key, item in targets:
        live = uploads.get(key) or item
        if already_commented(live):
            print(f"Already commented: {key}")
            skipped += 1
            continue
        yt_id = str(live.get("youtube_id") or "").strip()
        try:
            comment_id = post_comment(youtube, yt_id, text)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {key} ({yt_id}): {exc}", file=sys.stderr)
            continue
        live["kit_comment_id"] = comment_id
        live["kit_comment_posted_at"] = datetime.now(timezone.utc).isoformat()
        uploads[key] = live
        posted += 1
        print(f"Commented {key}: {live.get('url')} (id={comment_id})")
        print(f"  Pin in Studio (API cannot pin): https://studio.youtube.com/video/{yt_id}/comments")

    if posted:
        state["uploads"] = uploads
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_publish_state(state)
    print(f"Kit comments: {posted} posted, {skipped} skipped, {len(targets)} targeted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
