#!/usr/bin/env python3
"""Sync Sill Garden YouTube OAuth credentials to GitHub Actions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_common import oauth_client_path, token_path

REPO = "nivco/sill-garden"


def set_secret(name: str, value: str) -> None:
    result = subprocess.run(
        ["gh", "secret", "set", name, "--repo", REPO],
        input=value,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())


def main() -> int:
    token = token_path()
    client = oauth_client_path()
    if not token.is_file() or not client.is_file():
        print("Authorize first: python scripts/youtube_oauth_login.py --force", file=sys.stderr)
        return 1
    token_text = token.read_text(encoding="utf-8")
    client_text = client.read_text(encoding="utf-8")
    json.loads(token_text)
    json.loads(client_text)
    set_secret("YOUTUBE_USER_TOKEN_JSON", token_text)
    set_secret("YOUTUBE_OAUTH_CLIENT_JSON", client_text)
    print(f"Synced YouTube OAuth secrets -> {REPO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
