#!/usr/bin/env python3
"""Refresh uploaded Sill Garden video descriptions and tags from storyboards."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_access_gate import check
from youtube_common import (
    ROOT,
    build_description,
    default_tags,
    load_json,
    load_publish_state,
    save_publish_state,
)
from youtube_upload import refresh_video_assets, service


def automation_live() -> bool:
    return (os.environ.get("AUTOMATION_LIVE") or "").strip().lower() in {"1", "true", "yes"}


def storyboard_path(item: dict) -> Path | None:
    raw = str(item.get("storyboard") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview metadata without API calls")
    args = parser.parse_args()

    state = load_publish_state()
    uploads = state.get("uploads") or {}
    candidates: list[tuple[str, dict, Path, dict]] = []
    for video_id, item in sorted(uploads.items()):
        path = storyboard_path(item)
        youtube_id = str(item.get("youtube_id") or "").strip()
        if not path or not path.is_file():
            print(f"Skipping {video_id}: storyboard not found", file=sys.stderr)
            continue
        if not youtube_id:
            print(f"Skipping {video_id}: youtube_id missing", file=sys.stderr)
            continue
        candidates.append((video_id, item, path, load_json(path)))

    if not candidates:
        print("No uploaded videos with storyboards to refresh.")
        return 0

    if args.dry_run:
        for video_id, _, path, story in candidates:
            print(f"DRY RUN: {video_id}")
            print(f"tags: {', '.join(default_tags(story))}")
            print(build_description(story, path))
            print()
        return 0

    if not automation_live():
        print(
            "Refusing YouTube mutation: set AUTOMATION_LIVE=1 or use --dry-run.",
            file=sys.stderr,
        )
        return 1

    gate = check()
    if not gate.get("ready"):
        print(gate.get("error") or "YouTube access gate failed", file=sys.stderr)
        return 1

    youtube = service()
    changed = 0
    for video_id, item, path, story in candidates:
        if refresh_video_assets(str(item["youtube_id"]), story, path, youtube=youtube):
            item["metadata_refreshed_at"] = datetime.now(timezone.utc).isoformat()
            changed += 1
            print(f"Refreshed {video_id}")
        else:
            print(f"Already current: {video_id}")

    if changed:
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_publish_state(state)
    print(f"Metadata refresh complete: {changed} changed, {len(candidates) - changed} current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
