#!/usr/bin/env python3
"""Authorize uploads for the Sill Garden YouTube channel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_common import YOUTUBE_UPLOAD_SCOPES, oauth_client_path, token_path


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
    flow = InstalledAppFlow.from_client_secrets_file(str(client), YOUTUBE_UPLOAD_SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True, prompt="consent", access_type="offline")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(creds.to_json())
    data["scopes"] = sorted(set(data.get("scopes") or []) | set(YOUTUBE_UPLOAD_SCOPES))
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Saved Sill Garden upload token: {target}")
    print("Next: python scripts/youtube_access_gate.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
