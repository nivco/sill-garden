#!/usr/bin/env python3
"""Verify upload OAuth and report the exact YouTube channel it controls.

Run:
  python scripts/youtube_access_gate.py
  python scripts/youtube_access_gate.py --strict
  python scripts/youtube_access_gate.py --warn-only
"""

from __future__ import annotations

import argparse
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

FIX_STEPS = [
    "Local: .\\scripts\\fix_youtube_auth.ps1",
    "Or: python scripts/youtube_oauth_login.py --force && python scripts/youtube_token_sync.py",
    "Permanent: Google Cloud → OAuth consent screen → Publish app (Testing tokens die every ~7 days).",
]


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
        "next_steps": list(FIX_STEPS),
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
        if status["ready"]:
            status["next_steps"] = ["YouTube upload OAuth OK"]
        else:
            want = EXPECTED_CHANNEL_ID or "Sill Garden"
            status["error"] = (
                f"Token controls '{snippet.get('title')}' ({item.get('id')}), not {want}. "
                "Re-run: .\\scripts\\fix_youtube_auth.ps1 — in the browser, switch to the "
                "Sill Garden channel before approving (avatar menu → switch channel)."
            )
    except Exception as exc:  # noqa: BLE001
        status["error"] = str(exc)[:800]
        err_l = status["error"].lower()
        if "invalid_grant" in err_l or "expired or revoked" in err_l:
            status["next_steps"] = [
                "Refresh token revoked (common when OAuth app is still in Testing).",
                *FIX_STEPS,
            ]
    save_json(STATUS, status)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"ready={'true' if status['ready'] else 'false'}\n")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate YouTube publish on valid upload OAuth")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when not ready (default for bare run)")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Print warning and exit 0 when not ready (scheduled CI — skip upload, no red failure)",
    )
    args = parser.parse_args()

    status = check()
    print(json.dumps(status, indent=2))
    if status.get("ready"):
        print("YouTube access gate: upload OAuth OK")
        return 0

    msg = "YouTube access gate FAILED — upload OAuth not ready; publish skipped."
    if args.warn_only:
        print(f"WARNING: {msg}", file=sys.stderr)
        for step in status.get("next_steps") or []:
            print(f"  -> {step}", file=sys.stderr)
        return 0

    print(msg, file=sys.stderr)
    for step in status.get("next_steps") or []:
        print(f"  -> {step}", file=sys.stderr)
    # Bare run and --strict both fail closed.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
