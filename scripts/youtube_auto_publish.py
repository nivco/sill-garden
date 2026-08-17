#!/usr/bin/env python3
"""Build and upload the next unpublished storyboard as unlisted."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_common import PRODUCTS_YT, load_json, load_publish_state, story_id

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default=None)
    parser.add_argument("--force", action="store_true", help="Ignore auto_publish_enabled=false")
    args = parser.parse_args()

    queue = load_json(PRODUCTS_YT / "auto-queue.json") or {}
    if not args.force and not queue.get("auto_publish_enabled"):
        print(
            "YouTube auto-publish disabled (products/youtube/auto-queue.json "
            "auto_publish_enabled=false). Pass --force to override."
        )
        return 0

    privacy = args.privacy or str(queue.get("default_privacy") or "unlisted")
    if privacy not in ("private", "unlisted", "public"):
        privacy = "unlisted"

    uploaded = (load_publish_state().get("uploads") or {})
    pending: list[Path] = []
    for path in sorted(PRODUCTS_YT.glob("*/storyboard.json")):
        if story_id(load_json(path), path) not in uploaded:
            pending.append(path)
    if not pending:
        print("No unpublished Sill Garden storyboards.")
        return 0
    story = pending[0]
    command = [
        sys.executable,
        str(ROOT / "scripts" / "youtube_publish.py"),
        story.parent.name,
        "--build",
        "--privacy",
        privacy,
    ]
    if args.dry_run:
        command.append("--dry-run")
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
