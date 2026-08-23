#!/usr/bin/env python3
"""Verify upload OAuth and report the exact YouTube channel it controls."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_common import YOUTUBE_UPLOAD_SCOPES, load_dotenv, save_json, token_path

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "products" / "youtube" / "youtube-access-status.json"
EXPECTED_CHANNEL_ID = (os.environ.get("YOUTUBE_CHANNEL_ID") or "UCc31HDBMhoJtsmZYk0Fo56w").strip()
EXPECTED_CHANNEL_TITLE = "sill garden"


def _channel_ok(item: dict) -> bool:
    cid = (item.get("id") or "").strip()
    title = ((item.get("snippet") or {}).get("title") or "").strip().lower()
    if EXPECTED_CHANNEL_ID:
        return cid == EXPECTED_CHANNEL_ID
    return title == EXPECTED_CHANNEL_TITLE


def check() -> dict:
    status: dict = {
        "ready": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "channel": None,
        "error": None,
    }
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        path = token_path()
        if not path.is_file():
            raise RuntimeError("Missing token. Run: python scripts/youtube_oauth_login.py --force")
        creds = Credentials.from_authorized_user_file(str(path), YOUTUBE_UPLOAD_SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            path.write_text(creds.to_json() + "\n", encoding="utf-8")
        if not creds.valid:
            raise RuntimeError("YouTube token is invalid or expired")
        service = build("youtube", "v3", credentials=creds, cache_discovery=False)
        items = service.channels().list(part="id,snippet,statistics", mine=True).execute().get("items") or []
        if not items:
            raise RuntimeError("OAuth account has no selectable YouTube channel")
        item = items[0]
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        status["channel"] = {
            "id": item.get("id"),
            "title": snippet.get("title"),
            "handle": snippet.get("customUrl"),
            "subscribers": stats.get("subscriberCount"),
            "views": stats.get("viewCount"),
        }
        status["ready"] = _channel_ok(item)
        if not status["ready"]:
            want = EXPECTED_CHANNEL_ID or "Sill Garden"
            status["error"] = (
                f"Token controls '{snippet.get('title')}' ({item.get('id')}), not {want}. "
                "Re-run: .\\scripts\\fix_youtube_auth.ps1 — in the browser, switch to the "
                "Sill Garden channel before approving (avatar menu → switch channel)."
            )
    except Exception as exc:  # noqa: BLE001
        status["error"] = str(exc)[:800]
    save_json(STATUS, status)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"ready={'true' if status['ready'] else 'false'}\n")
    return status


def main() -> int:
    status = check()
    print(json.dumps(status, indent=2))
    return 0 if status["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
