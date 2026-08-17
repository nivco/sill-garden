#!/usr/bin/env python3
"""Load and patch Astro markdown guides under src/content/guides/."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES_DIR = ROOT / "src" / "content" / "guides"

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.DOTALL)


@dataclass
class GuideDoc:
    path: Path
    slug: str
    frontmatter: dict
    body: str

    @property
    def url(self) -> str:
        return f"https://sillgarden.com/guides/{self.slug}/"

    @property
    def title(self) -> str:
        return str(self.frontmatter.get("title") or self.slug)

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description") or "")


def _parse_scalar(raw: str):
    value = raw.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    return value


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict = {}
    current_list_key: str | None = None
    current_item: dict | None = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z0-9_]+:\s*", line) and not line.startswith(" "):
            if current_list_key and current_item is not None:
                meta.setdefault(current_list_key, []).append(current_item)
                current_item = None
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest == "":
                current_list_key = key
                meta[key] = []
                continue
            current_list_key = None
            meta[key] = _parse_scalar(rest)
            continue
        if current_list_key and line.strip().startswith("- "):
            if current_item is not None:
                meta.setdefault(current_list_key, []).append(current_item)
            item_raw = line.strip()[2:].strip()
            if ":" in item_raw:
                ik, _, iv = item_raw.partition(":")
                current_item = {ik.strip(): _parse_scalar(iv)}
            else:
                current_item = {"_": _parse_scalar(item_raw)}
            continue
        if current_list_key and current_item is not None and ":" in line:
            ik, _, iv = line.strip().partition(":")
            current_item[ik.strip()] = _parse_scalar(iv)
    if current_list_key and current_item is not None:
        meta.setdefault(current_list_key, []).append(current_item)
    return meta, match.group(2)


def dump_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for ik, iv in item.items():
                        if ik == "_":
                            continue
                        prefix = "- " if first else "  "
                        first = False
                        if isinstance(iv, bool):
                            rendered = "true" if iv else "false"
                        elif isinstance(iv, (int, float)):
                            rendered = str(iv)
                        else:
                            text = str(iv)
                            rendered = json_quote(text) if needs_quote(text) else text
                        lines.append(f"{prefix}{ik}: {rendered}")
                else:
                    lines.append(f"- {item}")
            continue
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            text = str(value)
            lines.append(f"{key}: {json_quote(text)}" if needs_quote(text) else f"{key}: {text}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def needs_quote(text: str) -> bool:
    return bool(re.search(r"[:#\[\]{},]|^\s|\s$", text)) or text.startswith(("*", "&", "!", "%", "@"))


def json_quote(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def load_guides() -> list[GuideDoc]:
    docs: list[GuideDoc] = []
    if not GUIDES_DIR.is_dir():
        return docs
    for path in sorted(GUIDES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        docs.append(GuideDoc(path=path, slug=path.stem, frontmatter=meta, body=body))
    return docs


def save_guide(doc: GuideDoc) -> None:
    doc.path.write_text(dump_frontmatter(doc.frontmatter) + doc.body.lstrip("\n"), encoding="utf-8")


def patch_guide_seo(slug: str, *, title: str | None = None, description: str | None = None) -> GuideDoc | None:
    docs = {d.slug: d for d in load_guides()}
    doc = docs.get(slug)
    if not doc:
        return None
    changed = False
    if title and title != doc.frontmatter.get("title"):
        doc.frontmatter["title"] = title
        changed = True
    if description and description != doc.frontmatter.get("description"):
        doc.frontmatter["description"] = description
        changed = True
    if changed:
        doc.frontmatter["updatedDate"] = date.today().isoformat()
        save_guide(doc)
    return doc if changed else None
