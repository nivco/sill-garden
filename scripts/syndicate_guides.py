#!/usr/bin/env python3
"""Syndicate Sill Garden guides to Dev.to and Hashnode."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import automation_live, load_dotenv, load_json, save_json

ROOT = Path(__file__).resolve().parents[1]
GUIDES_DIR = ROOT / "src" / "content" / "guides"
STATE_PATH = ROOT / "products" / "syndication" / "guides-state.json"
BASE_URL = "https://sillgarden.com"
DEVTO_API = "https://dev.to/api/articles"
HASHNODE_API = "https://gql.hashnode.com"
DEVTO_TAGS = ["apartment", "gardening", "indoorplants", "herbs"]
HASHNODE_TAGS = ["gardening", "apartment", "indoor-garden"]


def _frontmatter_value(raw: str) -> object:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def load_guide(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path.name}: missing YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"{path.name}: unterminated YAML frontmatter")
    metadata: dict[str, object] = {}
    for line in parts[1].splitlines():
        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = _frontmatter_value(value)
    metadata["slug"] = path.stem
    metadata["body"] = parts[2].strip()
    return metadata


def load_guides() -> list[dict]:
    guides: list[dict] = []
    for path in GUIDES_DIR.glob("*.md"):
        try:
            guides.append(load_guide(path))
        except (OSError, ValueError) as exc:
            print(f"Skipping {path.name}: {exc}", file=sys.stderr)
    return guides


def _date_ordinal(value: object) -> int:
    try:
        return date.fromisoformat(str(value)[:10]).toordinal()
    except ValueError:
        return 0


def ordered_guides(guides: list[dict]) -> list[dict]:
    def priority(guide: dict) -> tuple[int, int]:
        highlighted = bool(guide.get("featured")) or guide.get("type") == "comparison"
        return (_date_ordinal(guide.get("pubDate")), int(highlighted))

    return sorted(guides, key=priority, reverse=True)


def canonical_url(slug: str) -> str:
    return f"{BASE_URL}/guides/{slug}/"


def guide_markdown(guide: dict) -> str:
    canonical = canonical_url(str(guide["slug"]))
    body = str(guide["body"])
    body = body.replace("](/", f"]({BASE_URL}/")
    body = body.replace('src="/', f'src="{BASE_URL}/')
    footer = (
        "\n\n---\n\n"
        f"Originally published at [Sill Garden]({canonical}).\n\n"
        f"*Affiliate disclosure: Some links may earn us a commission. "
        f"[Read the disclosure]({BASE_URL}/disclosure/).*"
    )
    return body + footer


def http_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict | None = None,
) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SillGarden/1.0 (+https://sillgarden.com; syndication)",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return int(response.status), json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return int(exc.code), json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return int(exc.code), {"error": raw[:500]}
    except urllib.error.URLError as exc:
        return 599, {"error": str(exc.reason)}


def resolve_hashnode_publication_id() -> str:
    publication_id = (os.environ.get("HASHNODE_PUBLICATION_ID") or "").strip()
    if publication_id:
        return publication_id
    host = (os.environ.get("HASHNODE_PUBLICATION_HOST") or "").strip()
    token = (os.environ.get("HASHNODE_PAT") or "").strip()
    if not host or not token:
        return ""
    query = {
        "query": "query Publication($host: String!) { publication(host: $host) { id } }",
        "variables": {"host": host},
    }
    status, data = http_json(
        HASHNODE_API, headers={"Authorization": token}, body=query
    )
    if status >= 400:
        return ""
    return str(((data.get("data") or {}).get("publication") or {}).get("id") or "")


def post_devto(guide: dict, *, dry_run: bool) -> dict:
    title = str(guide.get("title") or guide["slug"])
    canonical = canonical_url(str(guide["slug"]))
    if dry_run:
        return {"dry_run": True, "title": title, "canonical_url": canonical}
    api_key = (os.environ.get("DEVTO_API_KEY") or "").strip()
    if not api_key:
        return {"skipped": "missing DEVTO_API_KEY"}
    payload = {
        "article": {
            "title": title,
            "body_markdown": guide_markdown(guide),
            "published": True,
            "canonical_url": canonical,
            "description": str(guide.get("description") or "")[:200],
            "tags": DEVTO_TAGS,
        }
    }
    status, data = http_json(
        DEVTO_API, headers={"api-key": api_key}, body=payload
    )
    if status >= 400:
        return {"error": data, "status": status}
    return {"id": data.get("id"), "url": data.get("url"), "status": status}


def post_hashnode(guide: dict, publication_id: str, *, dry_run: bool) -> dict:
    title = str(guide.get("title") or guide["slug"])
    canonical = canonical_url(str(guide["slug"]))
    if dry_run:
        return {"dry_run": True, "title": title, "originalArticleURL": canonical}
    token = (os.environ.get("HASHNODE_PAT") or "").strip()
    if not token:
        return {"skipped": "missing HASHNODE_PAT"}
    if not publication_id:
        return {"skipped": "missing HASHNODE_PUBLICATION_ID or HASHNODE_PUBLICATION_HOST"}
    mutation = {
        "query": (
            "mutation PublishPost($input: PublishPostInput!) { "
            "publishPost(input: $input) { post { id url slug } } }"
        ),
        "variables": {
            "input": {
                "publicationId": publication_id,
                "title": title,
                "contentMarkdown": guide_markdown(guide),
                "originalArticleURL": canonical,
                "tags": [{"slug": tag, "name": tag} for tag in HASHNODE_TAGS],
            }
        },
    }
    status, data = http_json(
        HASHNODE_API, headers={"Authorization": token}, body=mutation
    )
    if status >= 400 or data.get("errors"):
        return {"error": data.get("errors") or data, "status": status}
    post = ((data.get("data") or {}).get("publishPost") or {}).get("post") or {}
    if not post.get("id"):
        return {"error": "empty publishPost response", "status": status}
    return {"id": post.get("id"), "url": post.get("url"), "slug": post.get("slug")}


def was_posted(result: object) -> bool:
    return isinstance(result, dict) and bool(result.get("id") or result.get("url"))


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Syndicate Sill Garden guides")
    parser.add_argument("--max", type=int, default=2, dest="max_posts")
    parser.add_argument("--slug")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dry_run = args.dry_run or not automation_live()
    if dry_run and not args.dry_run:
        print("AUTOMATION_LIVE is not 1 — dry run.")

    state = load_json(STATE_PATH, {"guides": {}}) or {"guides": {}}
    guide_state: dict = state.setdefault("guides", {})
    guides = ordered_guides(load_guides())
    if args.slug:
        guides = [guide for guide in guides if guide["slug"] == args.slug]
        if not guides:
            print(f"Unknown guide slug: {args.slug}", file=sys.stderr)
            return 1

    publication_id = "" if dry_run else resolve_hashnode_publication_id()
    handled = 0
    changed = False
    for guide in guides:
        if handled >= max(0, args.max_posts):
            break
        slug = str(guide["slug"])
        entry = guide_state.get(slug, {})
        need_devto = not was_posted(entry.get("devto"))
        need_hashnode = not was_posted(entry.get("hashnode"))
        if not need_devto and not need_hashnode:
            continue

        print(f"\n=== {slug} ===")
        new_entry = dict(entry)
        new_entry["canonical"] = canonical_url(slug)
        entry_changed = False
        if need_devto:
            result = post_devto(guide, dry_run=dry_run)
            print(f"Dev.to: {json.dumps(result, ensure_ascii=False)}")
            if was_posted(result):
                new_entry["devto"] = result
                entry_changed = True
                changed = True
            if not dry_run:
                time.sleep(2)
        if need_hashnode:
            result = post_hashnode(guide, publication_id, dry_run=dry_run)
            print(f"Hashnode: {json.dumps(result, ensure_ascii=False)}")
            if was_posted(result):
                new_entry["hashnode"] = result
                entry_changed = True
                changed = True
            if not dry_run:
                time.sleep(2)
        if entry_changed and not dry_run:
            guide_state[slug] = new_entry
        handled += 1

    if changed and not dry_run:
        save_json(STATE_PATH, state)
        print(f"\nState saved: {STATE_PATH}")
    elif not dry_run:
        print("\nNo syndication state changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
