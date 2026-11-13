#!/usr/bin/env python3
"""Post kit + Amazon channel comments on Sill Garden videos.

YouTube Data API cannot pin comments. This posts (or updates) as the channel.
Pin in Studio if you want it sticky — paste is already live.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
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
    "CTmzbmQ5FAw",  # Bounty vs Harvest Short
    "F073SleZ9aA",  # Kratky Short
    "NSLsa1eJxko",  # AeroGarden vs Click & Grow Short
    "tGr1dpUCGXo",  # best countertop Short
    "s7KtScEHU6o",  # cheapest Short
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


def infer_format(key: str, item: dict) -> str:
    raw = str(item.get("format") or "").strip().lower()
    if raw in {"short", "long"}:
        return raw
    return "short" if key.startswith("short") else "long"


def all_targets(*, shorts_only: bool, limit: int | None) -> list[tuple[str, dict]]:
    state = load_publish_state()
    uploads = state.get("uploads") or {}
    views = views_by_id()
    rows: list[tuple[str, dict, int, int, int]] = []
    for key, item in uploads.items():
        yt_id = str(item.get("youtube_id") or "").strip()
        if not yt_id:
            continue
        fmt = infer_format(key, item)
        if shorts_only and fmt != "short":
            continue
        try:
            pri = PRIORITY_IDS.index(yt_id)
        except ValueError:
            pri = 100 + len(PRIORITY_IDS)
        # Shorts first (pri), then higher views, then longs after shorts.
        fmt_rank = 0 if fmt == "short" else 1
        rows.append((key, item, fmt_rank, pri, -views.get(yt_id, 0)))
    rows.sort(key=lambda row: (row[2], row[3], row[4], row[0]))
    picked = [(key, item) for key, item, *_ in rows]
    if limit is not None and limit > 0:
        return picked[:limit]
    return picked


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
    return str(
        (((resp.get("snippet") or {}).get("topLevelComment") or {}).get("id"))
        or resp.get("id")
        or ""
    )


def update_comment(youtube, comment_id: str, text: str) -> None:
    youtube.comments().update(
        part="snippet",
        body={"id": comment_id, "snippet": {"textOriginal": text}},
    ).execute()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max videos to touch (default: all when --all, else 8 Shorts)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Comment on every uploaded video (shorts + longs)",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Rewrite kit comments that already exist (e.g. add Amazon links)",
    )
    args = parser.parse_args()

    shorts_only = not args.all
    limit = args.limit
    if limit is None:
        limit = None if args.all else 8

    targets = all_targets(shorts_only=shorts_only, limit=limit)
    if not targets:
        print("No videos with youtube_id found.")
        return 0

    text = kit_comment_text()
    if args.dry_run:
        would_post = would_update = skip = 0
        for key, item in targets:
            if already_commented(item):
                if args.update_existing:
                    would_update += 1
                    status = "would update"
                else:
                    skip += 1
                    status = "skip (already posted)"
            else:
                would_post += 1
                status = "would post"
            print(f"DRY RUN [{status}]: {key} {item.get('youtube_id')} {item.get('url')}")
        print()
        print(text)
        print()
        print(
            f"Summary: {would_post} new, {would_update} updates, {skip} skip, "
            f"{len(targets)} targeted."
        )
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
    posted = updated = skipped = failed = 0
    pin_urls: list[str] = []

    for key, item in targets:
        live = uploads.get(key) or item
        yt_id = str(live.get("youtube_id") or "").strip()
        studio = f"https://studio.youtube.com/video/{yt_id}/comments"
        try:
            if already_commented(live):
                if not args.update_existing:
                    print(f"Already commented: {key}")
                    skipped += 1
                    continue
                comment_id = str(live.get("kit_comment_id") or "").strip()
                update_comment(youtube, comment_id, text)
                live["kit_comment_updated_at"] = datetime.now(timezone.utc).isoformat()
                uploads[key] = live
                updated += 1
                pin_urls.append(studio)
                print(f"Updated {key}: {live.get('url')}")
                print(f"  Pin in Studio: {studio}")
            else:
                comment_id = post_comment(youtube, yt_id, text)
                live["kit_comment_id"] = comment_id
                live["kit_comment_posted_at"] = datetime.now(timezone.utc).isoformat()
                uploads[key] = live
                posted += 1
                pin_urls.append(studio)
                print(f"Commented {key}: {live.get('url')} (id={comment_id})")
                print(f"  Pin in Studio: {studio}")
            # Soft pacing so a burst of inserts is less likely to trip quota/rate limits.
            time.sleep(0.35)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAILED {key} ({yt_id}): {exc}", file=sys.stderr)
            if "quotaExceeded" in str(exc):
                print("Stopping: YouTube daily quota exceeded.", file=sys.stderr)
                break

    if posted or updated:
        state["uploads"] = uploads
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_publish_state(state)

    print(
        f"Kit comments: {posted} posted, {updated} updated, {skipped} skipped, "
        f"{failed} failed, {len(targets)} targeted."
    )
    if pin_urls:
        print(f"Pin checklist ({len(pin_urls)} videos) — open each and Pin:")
        for url in pin_urls:
            print(f"  {url}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
