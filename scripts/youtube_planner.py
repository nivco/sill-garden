#!/usr/bin/env python3
"""Propose the next Sill Garden video from search demand and published guides."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from youtube_common import PRODUCTS_YT, load_json, save_json, story_id

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "products" / "analytics" / "latest.json"
GUIDES = ROOT / "src" / "content" / "guides"
CONTENT_HISTORY = PRODUCTS_YT / "content-history.json"
PUBLISH_STATE = PRODUCTS_YT / "publish-state.json"

STOP_WORDS = {
    "a",
    "and",
    "apartment",
    "best",
    "for",
    "garden",
    "gardens",
    "grow",
    "herbs",
    "how",
    "indoor",
    "of",
    "the",
    "to",
    "with",
}


def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    _, frontmatter, _ = text.split("---", 2)
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if line.startswith((" ", "\t", "-")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def guide_topics() -> list[dict]:
    topics: list[dict] = []
    for path in sorted(GUIDES.glob("*.md")):
        meta = parse_frontmatter(path)
        if not meta.get("title"):
            continue
        topics.append(
            {
                "slug": path.stem,
                "title": meta["title"],
                "description": meta.get("description", ""),
                "verdict": meta.get("verdict", ""),
                "image": meta.get("image", "/images/guide-windowsill.jpg").lstrip("/"),
            }
        )
    return topics


def query_terms() -> list[dict]:
    analytics = load_json(ANALYTICS, {})
    return (((analytics.get("sources") or {}).get("gsc") or {}).get("top_queries") or [])


def used_topics() -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    slugs: set[str] = set()
    for path in sorted(PRODUCTS_YT.glob("*/storyboard.json")):
        story = load_json(path, {})
        ids.add(story_id(story, path))
        if story.get("guide_slug"):
            slugs.add(str(story["guide_slug"]))

    state = load_json(PUBLISH_STATE, {"uploads": {}})
    for item_id, item in (state.get("uploads") or {}).items():
        ids.add(str(item_id))
        storyboard = item.get("storyboard")
        if storyboard:
            story_path = ROOT / str(storyboard)
            story = load_json(story_path, {})
            if story.get("guide_slug"):
                slugs.add(str(story["guide_slug"]))

    history = load_json(CONTENT_HISTORY, {"published": []})
    for item in history.get("published") or []:
        if item.get("id"):
            ids.add(str(item["id"]))
        if item.get("guide_slug"):
            slugs.add(str(item["guide_slug"]))
    return ids, slugs


def pending_storyboards() -> list[str]:
    uploaded = (load_json(PUBLISH_STATE, {"uploads": {}}).get("uploads") or {})
    return [
        story_id(load_json(path, {}), path)
        for path in sorted(PRODUCTS_YT.glob("*/storyboard.json"))
        if story_id(load_json(path, {}), path) not in uploaded
    ]


def score_topic(topic: dict, queries: list[dict]) -> tuple[float, list[str]]:
    haystack = f"{topic['title']} {topic['description']} {topic['slug']}".lower()
    topic_terms = set(re.findall(r"[a-z0-9]+", haystack))
    matched: list[str] = []
    score = 0.0
    for row in queries:
        query = str(row.get("query") or "").lower().strip()
        terms = {term for term in re.findall(r"[a-z0-9]+", query) if term not in STOP_WORDS}
        overlap = len(terms & topic_terms)
        if overlap:
            impressions = float(row.get("impressions") or 0)
            score += overlap * (1.0 + impressions)
            matched.append(query)
    # Prefer practical apartment questions when GSC is too sparse to distinguish topics.
    priorities = {
        "best-low-light-herbs-apartment": 4.0,
        "landlord-safe-indoor-garden-setup": 3.0,
        "best-countertop-garden-apartments": 2.5,
        "quiet-countertop-gardens-studios": 2.0,
        "grow-light-schedules-herbs": 1.5,
        "windowsill-herbs-without-kit": 1.0,
        "basil-countertop-first-harvest": 0.5,
    }
    return score + priorities.get(topic["slug"], 0.0), matched


def make_storyboard(topic: dict) -> dict:
    slug = topic["slug"]
    video_id = f"video-{slug}"
    short_title = re.sub(r"\s*\(2026\)\s*", " ", topic["title"]).strip()
    verdict = topic["verdict"] or topic["description"]
    image = topic["image"]
    return {
        "id": video_id,
        "title": f"{short_title} — Apartment Guide (2026)",
        "filename": f"sill-{slug}.mp4",
        "voice": "en-US-AvaMultilingualNeural",
        "guide_slug": slug,
        "utm_campaign": video_id,
        "description": topic["description"],
        "tags": [
            slug.replace("-", " "),
            "apartment gardening",
            "indoor herb garden",
            "small space garden",
            "sill garden",
        ],
        "slides": [
            {
                "type": "title",
                "chapter": "Quick answer",
                "title": short_title,
                "subtitle": topic["description"],
                "badge": "Apartment guide",
                "photo": image,
                "photo_right": "images/inline-counter-plant.jpg",
                "narration": (
                    f"{short_title}. Here is the practical Sill Garden answer for a small apartment, "
                    "without buying more equipment than you need."
                ),
            },
            {
                "type": "photo_bullets",
                "chapter": "Start here",
                "title": "Start with the apartment constraints",
                "photo": "images/inline-apartment.jpg",
                "bullets": [
                    "Measure the usable sill, shelf, or counter space",
                    "Check daylight before buying a grow light",
                    "Protect rental surfaces with trays and saucers",
                    "Choose a setup you can maintain every week",
                ],
                "narration": (
                    "Start with your real constraints: usable space, available daylight, water "
                    "protection, and how much weekly maintenance you will actually do."
                ),
            },
            {
                "type": "photo_bullets",
                "chapter": "What works",
                "title": "The simple setup that works",
                "photo": "images/inline-pots.jpg",
                "bullets": [
                    "Use the smallest reliable setup for the job",
                    "Put every pot or reservoir on a waterproof tray",
                    "Automate light timing before adding more plants",
                    "Watch plant response and adjust one thing at a time",
                ],
                "narration": (
                    "Keep the first setup simple. Protect the surface, automate the light schedule, "
                    "and adjust from what the plants show you instead of changing everything at once."
                ),
            },
            {
                "type": "photo_bullets",
                "chapter": "Avoid mistakes",
                "title": "Three expensive mistakes to avoid",
                "photo": "images/inline-shelf-herbs.jpg",
                "bullets": [
                    "Buying for maximum capacity instead of daily fit",
                    "Treating weak light as a watering problem",
                    "Ignoring noise, glare, or spill risk in a small room",
                ],
                "narration": (
                    "Avoid buying the largest system first. Weak light is not fixed by extra water, "
                    "and in a small room noise, glare, and spill risk matter every day."
                ),
            },
            {
                "type": "verdict",
                "chapter": "Verdict",
                "title": "The Sill Garden verdict",
                "body": verdict,
                "picks": [
                    "Start small and prove the routine first",
                    "Upgrade light or capacity only when the plants require it",
                ],
                "cta": f"Full guide → sillgarden.com/guides/{slug}",
                "photo": image,
                "narration": f"Our verdict: {verdict} Read the full step-by-step guide at Sill Garden dot com.",
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Write the best unused proposal")
    mode.add_argument("--dry-run", action="store_true", help="Print the proposal without writing (default)")
    args = parser.parse_args()

    pending = pending_storyboards()
    if args.write and pending:
        print(f"Planner skipped: unpublished storyboard already pending: {', '.join(pending)}")
        return 0

    ids, slugs = used_topics()
    queries = query_terms()
    proposals: list[tuple[float, dict, list[str]]] = []
    for topic in guide_topics():
        candidate_id = f"video-{topic['slug']}"
        if candidate_id in ids or topic["slug"] in slugs:
            continue
        score, matches = score_topic(topic, queries)
        proposals.append((score, topic, matches))
    proposals.sort(key=lambda item: (-item[0], item[1]["slug"]))
    if not proposals:
        print("No unused Sill Garden guide topics remain.")
        return 0

    score, topic, matches = proposals[0]
    story = make_storyboard(topic)
    proposal = {
        "proposal": {
            "id": story["id"],
            "guide_slug": story["guide_slug"],
            "title": story["title"],
            "score": round(score, 2),
            "matched_gsc_queries": matches,
        },
        "storyboard": story,
    }
    if not args.write:
        print(json.dumps(proposal, indent=2))
        return 0

    output = PRODUCTS_YT / story["id"] / "storyboard.json"
    if output.exists():
        print(f"Planner skipped: storyboard already exists: {output.relative_to(ROOT)}")
        return 0
    save_json(output, story)
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
