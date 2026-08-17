"""Small, dependency-free Bluesky AT Protocol helpers."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BSKY_XRPC = "https://bsky.social/xrpc"
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,!?;:)]}'\"…"


def link_facets_for_text(text: str) -> list[dict]:
    facets: list[dict] = []
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(TRAILING_PUNCTUATION)
        if not url:
            continue
        start = len(text[: match.start()].encode("utf-8"))
        end = len(text[: match.start() + len(url)].encode("utf-8"))
        facets.append(
            {
                "index": {"byteStart": start, "byteEnd": end},
                "features": [
                    {"$type": "app.bsky.richtext.facet#link", "uri": url}
                ],
            }
        )
    return facets


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def post_record(text: str) -> dict:
    record: dict = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": now_iso(),
    }
    facets = link_facets_for_text(text)
    if facets:
        record["facets"] = facets
    return record


def api(
    method: str,
    path: str,
    token: str | None = None,
    payload: dict | None = None,
    *,
    params: dict | None = None,
) -> dict:
    url = f"{BSKY_XRPC}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SillGarden/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Bluesky {path} failed ({exc.code}): {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Bluesky {path} unavailable: {exc.reason}") from exc


def login(identifier: str, app_password: str) -> dict:
    return api(
        "POST",
        "/com.atproto.server.createSession",
        payload={"identifier": identifier, "password": app_password},
    )
