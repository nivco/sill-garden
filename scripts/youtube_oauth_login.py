#!/usr/bin/env python3
"""Authorize uploads for the Sill Garden YouTube channel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_common import YOUTUBE_UPLOAD_SCOPES, load_dotenv, oauth_client_path, token_path

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    client = oauth_client_path()
    target = token_path()
    if not client.is_file():
        print(f"Missing OAuth desktop client: {client}", file=sys.stderr)
        return 1
    if target.is_file() and not args.force:
        print(f"Token already exists: {target}")
        print("Use --force to authorize a different channel.")
        return 0

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Install dependencies: pip install -r requirements-youtube.txt", file=sys.stderr)
        return 1

    print("IMPORTANT: in Google's account/channel chooser, select the Sill Garden channel.")
    print("If you see Maker Tool Stack, click your avatar (top right) -> Switch channel -> Sill Garden.")
    flow = InstalledAppFlow.from_client_secrets_file(str(client), YOUTUBE_UPLOAD_SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True, prompt="consent", access_type="offline")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(creds.to_json())
    data["scopes"] = sorted(set(data.get("scopes") or []) | set(YOUTUBE_UPLOAD_SCOPES))
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Saved Sill Garden upload token: {target}")

    from youtube_access_gate import check

    status = check()
    if not status.get("ready"):
        print(json.dumps(status, indent=2), file=sys.stderr)
        print(
            "\nWrong channel — deleted token. Re-run after switching to Sill Garden in the browser.",
            file=sys.stderr,
        )
        target.unlink(missing_ok=True)
        return 1
    print("Channel OK:", (status.get("channel") or {}).get("title"))
    print("Next: python scripts/youtube_token_sync.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
