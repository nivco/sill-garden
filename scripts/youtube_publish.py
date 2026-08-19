#!/usr/bin/env python3
"""Build (optional) and upload a Sill Garden video."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_common import find_storyboard, load_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="public")
    args = parser.parse_args()
    story = find_storyboard(args.video)
    if args.build:
        story_data = load_json(story)
        builder = "build_short_video.py" if story_data.get("format") == "short" else "build_visual_video.py"
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / builder), str(story)],
            cwd=ROOT,
            check=False,
        )
        if result.returncode:
            return result.returncode
    command = [
        sys.executable,
        str(ROOT / "scripts" / "youtube_upload.py"),
        story.parent.name,
        "--privacy",
        args.privacy,
    ]
    if args.dry_run:
        command.append("--dry-run")
    if args.force:
        command.append("--force")
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
