#!/usr/bin/env python3
"""Upload or publish one rendered Sill Garden video."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_access_gate import check
from youtube_common import (
    YOUTUBE_UPLOAD_SCOPES,
    affiliate_links,
    build_description,
    default_tags,
    find_storyboard,
    load_json,
    load_publish_state,
    output_mp4_path,
    save_publish_state,
    story_id,
    token_path,
)

ROOT = Path(__file__).resolve().parents[1]


def service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    path = token_path()
    creds = Credentials.from_authorized_user_file(str(path), YOUTUBE_UPLOAD_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json() + "\n", encoding="utf-8")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="unlisted")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    path = find_storyboard(args.video)
    story = load_json(path)
    video_id = story_id(story, path)
    mp4 = output_mp4_path(story, path)
    state = load_publish_state()
    existing = (state.get("uploads") or {}).get(video_id)
    if existing and not args.force:
        print(f"Already uploaded: {existing.get('url')}")
        return 0
    if not mp4.is_file():
        print(f"Missing video: {mp4}", file=sys.stderr)
        print(f"Build it: python scripts/build_visual_video.py {path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    description = build_description(story, path)
    tags = default_tags(story)
    paid = bool(affiliate_links(story))
    if args.dry_run:
        print(f"DRY RUN\nchannel: Sill Garden\nfile: {mp4}\nprivacy: {args.privacy}")
        print(f"title: {story.get('title')}\ntags: {', '.join(tags)}\n\n{description}")
        return 0

    gate = check()
    if not gate.get("ready"):
        print(gate.get("error") or "YouTube access gate failed", file=sys.stderr)
        return 1

    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": story.get("title") or video_id,
            "description": description,
            "tags": tags,
            "categoryId": "26",
        },
        "status": {
            "privacyStatus": args.privacy,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": False,
        },
    }
    parts = ["snippet", "status"]
    if paid:
        body["paidProductPlacementDetails"] = {"hasPaidProductPlacement": True}
        parts.append("paidProductPlacementDetails")
    request = service().videos().insert(
        part=",".join(parts),
        body=body,
        media_body=MediaFileUpload(str(mp4), chunksize=8 * 1024 * 1024, resumable=True),
    )
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            print(f"Upload {int(progress.progress() * 100)}%")
    youtube_id = response["id"]
    url = f"https://youtu.be/{youtube_id}"
    uploads = state.setdefault("uploads", {})
    uploads[video_id] = {
        "youtube_id": youtube_id,
        "url": url,
        "title": story.get("title") or video_id,
        "privacy": args.privacy,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "storyboard": str(path.relative_to(ROOT)).replace("\\", "/"),
        "format": story.get("format") or "long",
    }
    save_publish_state(state)
    print(f"Uploaded to Sill Garden: {url} ({args.privacy})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
