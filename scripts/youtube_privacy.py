#!/usr/bin/env python3
"""Change visibility for an uploaded Sill Garden video and update publish state."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_access_gate import check
from youtube_common import (
    YOUTUBE_UPLOAD_SCOPES,
    load_publish_state,
    save_publish_state,
    token_path,
)


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
    parser.add_argument("video", help="Storyboard id or YouTube id")
    parser.add_argument("privacy", choices=["private", "unlisted", "public"])
    args = parser.parse_args()

    gate = check()
    if not gate.get("ready"):
        print(gate.get("error") or "Sill Garden channel access failed", file=sys.stderr)
        return 1

    state = load_publish_state()
    uploads = state.setdefault("uploads", {})
    story_id = args.video
    meta = uploads.get(story_id)
    if not meta:
        match = next(
            ((key, value) for key, value in uploads.items() if value.get("youtube_id") == args.video),
            None,
        )
        if match:
            story_id, meta = match
    if not meta or not meta.get("youtube_id"):
        print(f"No uploaded video in publish state for: {args.video}", file=sys.stderr)
        return 1

    youtube_id = meta["youtube_id"]
    yt = service()
    current = yt.videos().list(part="snippet,status", id=youtube_id).execute().get("items") or []
    if not current:
        print(f"YouTube video not found: {youtube_id}", file=sys.stderr)
        return 1
    title = (current[0].get("snippet") or {}).get("title")
    yt.videos().update(
        part="status",
        body={
            "id": youtube_id,
            "status": {
                "privacyStatus": args.privacy,
                "selfDeclaredMadeForKids": False,
            },
        },
    ).execute()
    meta["privacy"] = args.privacy
    if args.privacy == "public":
        meta["published_at"] = datetime.now(timezone.utc).isoformat()
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_publish_state(state)
    print(f"{title}: {args.privacy} -> https://youtu.be/{youtube_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
