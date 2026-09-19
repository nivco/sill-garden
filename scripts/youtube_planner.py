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
    "vs",
    "2026",
}

# Adjacent angles when every published guide already has a video+short.
# Each row: synthetic slug, title, nearest real guide for CTA, image hint.
RELATED_TOPIC_SEEDS: list[dict] = [
    {
        "slug": "related-basil-vs-mint-windowsill",
        "title": "Basil vs Mint on a Windowsill (2026) — Which First?",
        "description": "Which herb to start on a small apartment windowsill — basil for cooking speed vs mint for forgiveness.",
        "verdict": "Start mint if you forget water; start basil if you cook often and can give brighter light.",
        "guide_slug": "mint-windowsill-first-harvest",
        "image": "images/inline-seedlings.jpg",
    },
    {
        "slug": "related-grow-light-vs-sunny-window",
        "title": "Grow Light vs Sunny Window for Apartment Herbs (2026)",
        "description": "When a cheap clip light beats hoping for a south window — and when natural light is enough.",
        "verdict": "If stems stretch in a week, add a timer light. A bright window alone rarely enough for basil.",
        "guide_slug": "grow-light-schedules-herbs",
        "image": "images/inline-apartment.jpg",
    },
    {
        "slug": "related-hydroponic-vs-soil-apartment",
        "title": "Hydroponic vs Soil Herbs in an Apartment (2026)",
        "description": "Kratky jars and countertop pods vs soil pots — mess, speed, and landlord-safe tradeoffs.",
        "verdict": "Soil pots are quieter and cheaper to start; hydro wins if you want faster leafy greens with a tray.",
        "guide_slug": "kratky-jar-herbs-apartment",
        "image": "images/inline-pots.jpg",
    },
    {
        "slug": "related-first-month-countertop-garden",
        "title": "First Month With a Countertop Garden (What Actually Happens)",
        "description": "Week-by-week expectations for pods, algae, stretchy stems, and the first harvest in a small kitchen.",
        "verdict": "Expect slow week 1–2. Fix light before buying more pods. Harvest lightly once leaves fill out.",
        "guide_slug": "countertop-garden-system-guide",
        "image": "images/inline-counter-plant.jpg",
    },
    {
        "slug": "related-stop-overwatering-indoor-herbs",
        "title": "Stop Overwatering Indoor Herbs (Apartment Fix)",
        "description": "Yellow leaves, soggy soil, and tray overflow — the renter-safe watering routine that stops killing basil.",
        "verdict": "Water less, tray always, check weight not schedule. Yellow lower leaves usually mean wet roots or weak light.",
        "guide_slug": "yellow-leaves-leggy-seedlings-indoor-herbs",
        "image": "images/inline-greenery.jpg",
    },
    {
        "slug": "related-best-herbs-for-renters",
        "title": "Best Herbs for Renters (No Drill, No Damage)",
        "description": "Landlord-safe herbs and setups that sit on trays — no wall mounts, no permanent grow tents.",
        "verdict": "Mint, chives, and parsley on a trayed sill or quiet countertop kit beat rosemary in most rentals.",
        "guide_slug": "landlord-safe-indoor-garden-setup",
        "image": "images/inline-shelf-herbs.jpg",
    },
    {
        "slug": "related-quietest-indoor-garden",
        "title": "Quietest Indoor Garden for Studios (2026)",
        "description": "Pump noise, fan hum, and light glare — what to buy if you sleep in the same room as the plants.",
        "verdict": "Skip loud aerator pumps. Prefer passive Kratky or soil trays; schedule lights for waking hours.",
        "guide_slug": "quiet-countertop-gardens-studios",
        "image": "images/inline-apartment.jpg",
    },
    {
        "slug": "related-pod-refills-worth-it",
        "title": "Are Countertop Garden Pod Refills Worth It?",
        "description": "True monthly cost of branded pods vs seed-your-own — when refills make sense for apartment cooks.",
        "verdict": "Refills are fine for convenience herbs you eat weekly; switch to seed for high-volume basil.",
        "guide_slug": "countertop-garden-pod-refill-cost",
        "image": "images/inline-pots.jpg",
    },
    {
        "slug": "related-click-and-grow-vs-aerogarden-2026",
        "title": "Click and Grow vs AeroGarden in 2026 — Honest Pick",
        "description": "Footprint, noise, pods, and who should buy which for a small kitchen counter.",
        "verdict": "Choose Click and Grow for simpler quiet setups; AeroGarden when you want more control and capacity.",
        "guide_slug": "aerogarden-vs-click-and-grow",
        "image": "images/guide-windowsill.jpg",
    },
    {
        "slug": "related-indoor-herbs-without-south-window",
        "title": "Indoor Herbs Without a South Window (2026)",
        "description": "Low-light picks and the minimum clip-light setup when your apartment only has a dim sill.",
        "verdict": "Skip rosemary. Start mint/chives and add a $20 timer light before buying a big kit.",
        "guide_slug": "best-low-light-herbs-apartment",
        "image": "images/inline-seedlings-alt.jpg",
    },
    {
        "slug": "related-apartment-garden-on-a-budget",
        "title": "Apartment Herb Garden Under $40 (2026)",
        "description": "Cheapest path that still works — jars, trays, one light — without a $200 countertop system.",
        "verdict": "Tray + pots + one clip light beats a cheap no-light kit. Spend on light before branding.",
        "guide_slug": "cheapest-indoor-herb-garden-apartment",
        "image": "images/inline-pots.jpg",
    },
    {
        "slug": "related-when-to-harvest-basil-indoors",
        "title": "When to Harvest Basil Indoors (Don't Wait Too Long)",
        "description": "Pinching timing so indoor basil bushes instead of bolting on a countertop or sill.",
        "verdict": "Pinch above a leaf pair once you have 6+ true leaves. Never strip the whole stem.",
        "guide_slug": "basil-countertop-first-harvest",
        "image": "images/inline-greenery.jpg",
    },
]


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


def used_ids() -> set[str]:
    ids: set[str] = set()
    for path in sorted(PRODUCTS_YT.glob("*/storyboard.json")):
        story = load_json(path, {})
        ids.add(story_id(story, path))
        slug = str(story.get("guide_slug") or "")
        if slug:
            prefix = "short-" if str(story.get("format") or "").lower() == "short" else "video-"
            ids.add(f"{prefix}{slug}")
    state = load_json(PUBLISH_STATE, {"uploads": {}})
    for item_id, item in (state.get("uploads") or {}).items():
        ids.add(str(item_id))
        storyboard = item.get("storyboard")
        if storyboard:
            story_path = ROOT / str(storyboard)
            story = load_json(story_path, {})
            slug = str(story.get("guide_slug") or item.get("guide_slug") or "")
            if slug:
                prefix = "short-" if str(item.get("format") or story.get("format") or "").lower() == "short" else "video-"
                ids.add(f"{prefix}{slug}")
    history = load_json(CONTENT_HISTORY, {"published": []})
    for item in history.get("published") or []:
        if item.get("id"):
            ids.add(str(item["id"]))
        if item.get("guide_slug"):
            prefix = "short-" if str(item.get("format") or "").lower() == "short" else "video-"
            ids.add(f"{prefix}{item['guide_slug']}")
    return ids


def pending_storyboards(*, shorts: bool | None = None) -> list[str]:
    uploaded = (load_json(PUBLISH_STATE, {"uploads": {}}).get("uploads") or {})
    pending: list[str] = []
    for path in sorted(PRODUCTS_YT.glob("*/storyboard.json")):
        story = load_json(path, {})
        is_short = str(story.get("format") or "").lower() == "short"
        if shorts is True and not is_short:
            continue
        if shorts is False and is_short:
            continue
        if story_id(story, path) not in uploaded:
            pending.append(story_id(story, path))
    return pending


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


def _photo_file(image: str) -> str:
    name = str(image or "images/guide-windowsill.jpg").replace("\\", "/").lstrip("/")
    if name.startswith("images/"):
        name = name[len("images/") :]
    return name or "guide-windowsill.jpg"


def _short_headline(title: str) -> str:
    clean = re.sub(r"\s*\(2026\)\s*", " ", title).strip()
    if " — " in clean:
        left, right = clean.split(" — ", 1)
        return f"{left.strip()}\n{right.strip()[:42]}"
    words = clean.split()
    if len(words) <= 5:
        return clean
    mid = max(2, len(words) // 2)
    return " ".join(words[:mid]) + "\n" + " ".join(words[mid:])


def make_short_storyboard(topic: dict, *, storyboard_id: str | None = None) -> dict:
    slug = topic.get("guide_slug") or topic["slug"]
    short_id = storyboard_id or f"short-{topic['slug']}"
    short_title = re.sub(r"\s*\(2026\)\s*", " ", topic["title"]).strip()
    verdict = topic["verdict"] or topic["description"]
    photo = _photo_file(topic["image"])
    return {
        "id": short_id,
        "format": "short",
        "title": f"{short_title} #Shorts",
        "filename": f"sill-{topic['slug']}-short.mp4",
        "voice": "en-US-AvaMultilingualNeural",
        "guide_slug": slug,
        "related_topic": bool(topic.get("related")),
        "utm_campaign": short_id,
        "description": topic["description"],
        "tags": [
            slug.replace("-", " "),
            "apartment gardening",
            "indoor herb garden",
            "sill garden",
            "shorts",
        ],
        "slides": [
            {
                "eyebrow": "APARTMENT GUIDE",
                "headline": _short_headline(short_title),
                "subhead": topic["description"][:110],
                "photo": photo,
                "accent": "START HERE",
                "narration": (
                    f"{short_title}. The Sill Garden answer for a small apartment, "
                    "without buying more equipment than you need."
                ),
            },
            {
                "eyebrow": "DO THIS FIRST",
                "headline": "Match the setup\nto your space.",
                "subhead": "Light, noise, and spill risk matter more than pod count.",
                "photo": "inline-apartment.jpg",
                "accent": "CONSTRAINTS",
                "narration": (
                    "Start with usable space, daylight, and a tray that protects the rental surface. "
                    "Then pick the smallest setup that still grows what you cook."
                ),
            },
            {
                "eyebrow": "SKIP THIS",
                "headline": "Don't buy the\nbiggest kit first.",
                "subhead": "Weak light is not a watering problem.",
                "photo": "inline-pots.jpg",
                "accent": "COMMON MISTAKE",
                "narration": (
                    "Skip the largest system until the plants prove they need it. "
                    "Stretching stems usually mean more light, not more water."
                ),
            },
            {
                "eyebrow": "THE VERDICT",
                "headline": "Start small.\nProve the routine.",
                "subhead": verdict[:140],
                "photo": "inline-greenery.jpg",
                "accent": "FULL GUIDE BELOW",
                "narration": f"Our verdict: {verdict} Full guide on Sill Garden dot com.",
            },
        ],
    }


# Search-shaped titles. Generic "Apartment Guide (2026)" slideshows got ~0 views after Sep 5.
SEARCH_TITLES = {
    "compare-aerogarden-models": "AeroGarden Bounty vs Harvest (2026) — Which Should You Buy?",
    "aerogarden-vs-click-and-grow": "AeroGarden vs Click and Grow (2026) — Which Is Better?",
    "best-countertop-garden-apartments": "Best Countertop Garden for Apartments (2026)",
    "cheapest-indoor-herb-garden-apartment": "Cheapest Indoor Herb Garden Under $50 (2026)",
    "click-and-grow-vs-idoo-auk": "Click and Grow vs iDOO vs Auk (2026)",
}


def _search_title(topic: dict) -> str:
    slug = topic["slug"]
    if slug in SEARCH_TITLES:
        return SEARCH_TITLES[slug]
    short_title = re.sub(r"\s*\(2026\)\s*", " ", topic["title"]).strip()
    short_title = re.sub(r"\s*—\s*Apartment Guide\s*$", "", short_title).strip()
    if "(2026)" not in short_title and len(short_title) < 70:
        return f"{short_title} (2026)"
    return short_title


def make_storyboard(topic: dict, *, storyboard_id: str | None = None) -> dict:
    # Related topics keep a synthetic slug for the video id but CTA to nearest real guide.
    slug = topic.get("guide_slug") or topic["slug"]
    video_id = storyboard_id or f"video-{topic['slug']}"
    short_title = topic["title"] if topic.get("related") else _search_title(topic)
    verdict = topic["verdict"] or topic["description"]
    image = topic["image"]
    return {
        "id": video_id,
        "title": short_title,
        "filename": f"sill-{topic['slug']}.mp4",
        "voice": "en-US-AvaMultilingualNeural",
        "guide_slug": slug,
        "related_topic": bool(topic.get("related")),
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


def _nearest_guide(query: str, guides: list[dict]) -> dict | None:
    terms = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if t not in STOP_WORDS}
    if not terms:
        return None
    best: dict | None = None
    best_n = 0
    for g in guides:
        hay = f"{g['title']} {g['description']} {g['slug']}".lower()
        gterms = set(re.findall(r"[a-z0-9]+", hay))
        n = len(terms & gterms)
        if n > best_n:
            best_n = n
            best = g
    return best if best_n >= 1 else None


def related_topics_from_seeds() -> list[dict]:
    guides = {g["slug"]: g for g in guide_topics()}
    out: list[dict] = []
    for seed in RELATED_TOPIC_SEEDS:
        nearest = guides.get(seed["guide_slug"]) or next(iter(guides.values()), None)
        if not nearest:
            continue
        out.append(
            {
                "slug": seed["slug"],
                "title": seed["title"],
                "description": seed["description"],
                "verdict": seed["verdict"],
                "image": seed.get("image") or nearest.get("image") or "images/guide-windowsill.jpg",
                "guide_slug": seed["guide_slug"],
                "related": True,
            }
        )
    return out


def related_topics_from_gsc(queries: list[dict]) -> list[dict]:
    """Turn search queries that aren't already a published guide into related video topics."""
    guides = guide_topics()
    guide_slugs = {g["slug"] for g in guides}
    # Queries already well-covered by a dedicated guide slug / search title
    covered_bits = set()
    for g in guides:
        covered_bits |= set(re.findall(r"[a-z0-9]+", g["slug"].replace("-", " ")))
        covered_bits |= set(re.findall(r"[a-z0-9]+", g["title"].lower()))

    out: list[dict] = []
    seen_slugs: set[str] = set()
    for row in sorted(queries, key=lambda r: -float(r.get("impressions") or 0)):
        query = str(row.get("query") or "").strip()
        if len(query) < 12:
            continue
        q_terms = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if t not in STOP_WORDS}
        if len(q_terms) < 2:
            continue
        # Skip if this query is basically an existing guide title
        slug = f"related-{slugify(query)[:48]}"
        if slug in seen_slugs or slug in guide_slugs:
            continue
        nearest = _nearest_guide(query, guides)
        if not nearest:
            continue
        # Prefer queries that only partially overlap existing guides (new angle).
        overlap = len(q_terms & covered_bits) / max(1, len(q_terms))
        if overlap >= 0.9:
            continue
        impr = float(row.get("impressions") or 0)
        title = query.strip()
        if "(2026)" not in title and len(title) < 70:
            title = f"{title} (2026)"
        title = title[:90]
        out.append(
            {
                "slug": slug,
                "title": title[:1].upper() + title[1:],
                "description": (
                    f"Practical apartment answer for “{query}” — small-space setup, "
                    "what to buy first, and what to skip."
                ),
                "verdict": (
                    nearest.get("verdict")
                    or "Start small, fix light before gear, and protect rental surfaces with a tray."
                ),
                "image": nearest.get("image") or "images/guide-windowsill.jpg",
                "guide_slug": nearest["slug"],
                "related": True,
                "gsc_query": query,
                "gsc_impressions": impr,
            }
        )
        seen_slugs.add(slug)
        if len(out) >= 12:
            break
    return out


def ranked_topics(*, prefix: str) -> list[tuple[float, dict, list[str], str]]:
    """Rank topics: fresh guides → related angles → dated remakes.

    Returns (score, topic, matched_queries, storyboard_id).
    """
    from datetime import date

    ids = used_ids()
    queries = query_terms()
    fresh: list[tuple[float, dict, list[str], str]] = []
    related: list[tuple[float, dict, list[str], str]] = []
    remakes: list[tuple[float, dict, list[str], str]] = []
    stamp = date.today().strftime("%Y%m%d")

    for topic in guide_topics():
        base_id = f"{prefix}{topic['slug']}"
        score, matches = score_topic(topic, queries)
        if base_id not in ids:
            fresh.append((score, topic, matches, base_id))
            continue
        remake_id = f"{base_id}-{stamp}"
        if remake_id in ids:
            continue
        remakes.append((score * 0.55, topic, matches, remake_id))

    for topic in related_topics_from_seeds() + related_topics_from_gsc(queries):
        base_id = f"{prefix}{topic['slug']}"
        if base_id in ids:
            # Allow one dated related remake only if seed already used
            base_id = f"{base_id}-{stamp}"
            if base_id in ids:
                continue
        score, matches = score_topic(topic, queries)
        # Boost GSC-backed related topics
        if topic.get("gsc_impressions"):
            score += float(topic["gsc_impressions"]) * 2.0
        else:
            score += 8.0  # curated seeds beat blind remakes
        if topic.get("gsc_query"):
            matches = list(dict.fromkeys([topic["gsc_query"], *matches]))
        related.append((score, topic, matches, base_id))

    fresh.sort(key=lambda item: (-item[0], item[1]["slug"]))
    related.sort(key=lambda item: (-item[0], item[1]["slug"]))
    remakes.sort(key=lambda item: (-item[0], item[1]["slug"]))
    return fresh or related or remakes


def write_storyboard(story: dict) -> Path | None:
    output = PRODUCTS_YT / story["id"] / "storyboard.json"
    if output.exists():
        print(f"Planner skipped: storyboard already exists: {output.relative_to(ROOT)}")
        return None
    save_json(output, story)
    print(f"Wrote {output.relative_to(ROOT)}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Write the next unused long-form storyboard")
    mode.add_argument("--write-short", action="store_true", help="Write the next unused Short storyboard")
    mode.add_argument("--write-all", action="store_true", help="Write all unused video + Short storyboards")
    mode.add_argument("--dry-run", action="store_true", help="Print the proposal without writing (default)")
    args = parser.parse_args()

    if args.write_all:
        written = 0
        for prefix, factory in (("video-", make_storyboard), ("short-", make_short_storyboard)):
            for _score, topic, _matches, sid in ranked_topics(prefix=prefix):
                if write_storyboard(factory(topic, storyboard_id=sid)):
                    written += 1
        print(f"Wrote {written} storyboards")
        return 0

    shorts = args.write_short
    prefix = "short-" if shorts else "video-"
    pending = pending_storyboards(shorts=shorts)
    if (args.write or args.write_short) and pending:
        print(f"Planner skipped: unpublished storyboard already pending: {', '.join(pending)}")
        return 0

    proposals = ranked_topics(prefix=prefix)
    if not proposals:
        print("No unused Sill Garden guide or related topics remain.")
        return 0

    score, topic, matches, sid = proposals[0]
    story = (
        make_short_storyboard(topic, storyboard_id=sid)
        if shorts
        else make_storyboard(topic, storyboard_id=sid)
    )
    proposal = {
        "proposal": {
            "id": story["id"],
            "guide_slug": story["guide_slug"],
            "title": story["title"],
            "score": round(score, 2),
            "matched_gsc_queries": matches[:8],
            "related": bool(topic.get("related")),
            "remake": (not topic.get("related")) and sid != f"{prefix}{topic['slug']}",
        },
        "storyboard": story,
    }
    if not (args.write or args.write_short):
        print(json.dumps(proposal, indent=2))
        return 0

    write_storyboard(story)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
