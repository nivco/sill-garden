"""Shared Sill Garden YouTube build, attribution, and OAuth helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_YT = ROOT / "products" / "youtube"
PUBLISH_STATE = PRODUCTS_YT / "publish-state.json"

YOUTUBE_UPLOAD_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_json(path: Path, default=None):
    if not path.is_file():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def find_storyboard(video_ref: str) -> Path:
    ref = video_ref.strip().replace("\\", "/")
    direct = Path(ref)
    if direct.suffix == ".json":
        path = direct if direct.is_absolute() else ROOT / direct
        if path.is_file():
            return path.resolve()
    candidates = sorted(PRODUCTS_YT.glob("*/storyboard.json"))
    exact = [p for p in candidates if p.parent.name == ref]
    partial = [p for p in candidates if ref in p.parent.name]
    matches = exact or partial
    if len(matches) == 1:
        return matches[0].resolve()
    if len(matches) > 1:
        raise FileNotFoundError(f"Ambiguous video '{video_ref}': {', '.join(p.parent.name for p in matches)}")
    raise FileNotFoundError(f"No storyboard for '{video_ref}' under {PRODUCTS_YT}")


def story_id(story: dict, path: Path) -> str:
    return str(story.get("id") or path.parent.name)


def output_mp4_path(story: dict, path: Path) -> Path:
    return path.parent / str(story.get("filename") or story.get("output_mp4") or f"{story_id(story, path)}.mp4")


def add_utm(url: str, campaign: str, medium: str = "video") -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("utm_source", "youtube")
    query.setdefault("utm_medium", medium)
    query.setdefault("utm_campaign", campaign)
    return urlunparse(parsed._replace(query=urlencode(query)))


def campaign_name(story: dict, path: Path) -> str:
    return str(story.get("utm_campaign") or story_id(story, path))


def guide_url(story: dict, path: Path) -> str:
    slug = str(story.get("guide_slug") or "aerogarden-vs-click-and-grow").strip("/")
    return add_utm(f"https://sillgarden.com/guides/{slug}/", campaign_name(story, path))


def affiliate_links(story: dict) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for item in story.get("affiliate_links") or []:
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        if label and url:
            links.append((label, url))
    return links


def build_description(story: dict, path: Path) -> str:
    campaign = campaign_name(story, path)
    lines = [
        str(story.get("description") or "").strip(),
        "",
        "Full comparison and apartment setup notes:",
        guide_url(story, path),
        "",
        "More apartment garden guides:",
        add_utm("https://sillgarden.com/guides/", campaign),
    ]
    links = affiliate_links(story)
    if links:
        lines.extend(["", "Product links:"])
        for label, url in links:
            lines.extend([f"• {label}", url])
    lines.extend(
        [
            "",
            "As an Amazon Associate I earn from qualifying purchases. Some links may also use "
            "direct partner programs. Recommendations are based on apartment fit, noise, footprint, "
            "and refill cost.",
            "",
            "Production note: visuals and synthetic narration are AI-assisted; product comparisons "
            "are editorial.",
        ]
    )
    return "\n".join(line for line in lines if line is not None).strip()


def default_tags(story: dict) -> list[str]:
    tags = [str(tag).strip() for tag in story.get("tags") or [] if str(tag).strip()]
    defaults = ["sill garden", "apartment gardening", "indoor herb garden", "countertop garden"]
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags + defaults:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            result.append(tag)
    return result[:15]


def _json_env_path(env_name: str, filename: str, fallback: Path) -> Path:
    load_dotenv()
    raw = (os.environ.get(env_name) or "").strip()
    if raw.startswith("{"):
        folder = Path(os.environ.get("RUNNER_TEMP") or os.environ.get("TEMP") or tempfile.gettempdir())
        path = folder / filename
        path.write_text(json.dumps(json.loads(raw), indent=2) + "\n", encoding="utf-8")
        return path
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else ROOT / path
    return fallback


def token_path() -> Path:
    return _json_env_path(
        "YOUTUBE_USER_TOKEN_JSON",
        "sill-youtube-user-token.json",
        ROOT / "secrets" / "youtube-user-token.json",
    )


def oauth_client_path() -> Path:
    load_dotenv()
    raw = (os.environ.get("YOUTUBE_OAUTH_CLIENT_JSON") or "").strip()
    if not raw:
        # Reuse the MTS desktop client locally; the Sill token remains separate.
        fallback = ROOT.parent / "makertoolstack" / "secrets" / "google-oauth-client.json"
    else:
        fallback = ROOT / "secrets" / "google-oauth-client.json"
    return _json_env_path("YOUTUBE_OAUTH_CLIENT_JSON", "sill-youtube-oauth-client.json", fallback)


def load_publish_state() -> dict:
    return load_json(PUBLISH_STATE, {"uploads": {}})


def save_publish_state(value: dict) -> None:
    save_json(PUBLISH_STATE, value)
