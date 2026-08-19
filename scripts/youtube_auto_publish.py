#!/usr/bin/env python3
"""Build and upload the next unpublished storyboard (daily cadence)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_common import PRODUCTS_YT, load_json, load_publish_state, save_publish_state, story_id

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = PRODUCTS_YT / "auto-queue.json"


def _stamp_date(value: str) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def last_upload_date(uploads: dict, *, shorts: bool) -> date | None:
    dates: list[date] = []
    for row in uploads.values():
        is_short = str(row.get("format") or "").lower() == "short"
        if shorts != is_short:
            continue
        parsed = _stamp_date(str(row.get("published_at") or row.get("uploaded_at") or ""))
        if parsed:
            dates.append(parsed)
    return max(dates) if dates else None


def uploads_today(uploads: dict) -> int:
    today = datetime.now(timezone.utc).date()
    count = 0
    for row in uploads.values():
        parsed = _stamp_date(str(row.get("uploaded_at") or row.get("published_at") or ""))
        if parsed == today:
            count += 1
    return count


def pending_storyboards(*, shorts: bool) -> list[Path]:
    uploaded = load_publish_state().get("uploads") or {}
    pending: list[Path] = []
    for path in sorted(PRODUCTS_YT.glob("*/storyboard.json")):
        story = load_json(path) or {}
        is_short = str(story.get("format") or "").lower() == "short"
        if shorts != is_short:
            continue
        if story_id(story, path) in uploaded:
            continue
        pending.append(path)
    return pending


def eligible(last: date | None, min_days: int, *, force: bool) -> tuple[bool, str]:
    if force:
        return True, "forced"
    if last is None:
        return True, "no prior upload"
    wait_until = last + timedelta(days=max(1, min_days))
    today = datetime.now(timezone.utc).date()
    if today < wait_until:
        return False, f"next eligible {wait_until.isoformat()} (last {last.isoformat()})"
    return True, "eligible"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default=None)
    parser.add_argument("--force", action="store_true", help="Ignore auto_publish_enabled and interval")
    parser.add_argument("--short-slot", action="store_true", help="Upload the next unpublished Short")
    args = parser.parse_args()

    queue = load_json(QUEUE_PATH) or {}
    if not args.force and not queue.get("auto_publish_enabled"):
        print(
            "YouTube auto-publish disabled (products/youtube/auto-queue.json "
            "auto_publish_enabled=false). Pass --force to override."
        )
        return 0

    privacy = args.privacy or str(queue.get("default_privacy") or "public")
    if privacy not in ("private", "unlisted", "public"):
        privacy = "public"

    state = load_publish_state()
    uploads = state.get("uploads") or {}
    daily_max = max(1, int(queue.get("max_uploads_per_day") or 2))
    done_today = uploads_today(uploads)
    if done_today >= daily_max and not args.force:
        print(f"Skipped — daily cap reached ({done_today}/{daily_max})")
        return 0

    min_days = max(1, int(queue.get("min_days_between") or 1))
    last = last_upload_date(uploads, shorts=args.short_slot)
    ok, reason = eligible(last, min_days, force=args.force)
    if not ok:
        print(f"Skipped {'Short' if args.short_slot else 'video'} — {reason}")
        return 0

    pending = pending_storyboards(shorts=args.short_slot)
    if not pending:
        print("No unpublished Sill Garden Shorts." if args.short_slot else "No unpublished Sill Garden storyboards.")
        return 0

    story = pending[0]
    print(f"Next {'Short' if args.short_slot else 'video'}: {story.parent.name} ({reason})")
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
    code = subprocess.call(command, cwd=ROOT)
    if code == 0 and not args.dry_run:
        refreshed = load_publish_state()
        refreshed["next_eligible_date"] = (
            datetime.now(timezone.utc).date() + timedelta(days=min_days)
        ).isoformat()
        save_publish_state(refreshed)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
