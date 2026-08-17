#!/usr/bin/env python3
"""CTR-first SEO proposals for Sill Garden markdown guides."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from guide_content import load_guides


QUERY_GUIDE_RULES: list[tuple[tuple[str, ...], str]] = [
    (("aerogarden", "click and grow", "click & grow"), "aerogarden-vs-click-and-grow"),
    (("low light", "north facing", "dim window"), "best-low-light-herbs-apartment"),
    (("landlord", "rental", "deposit"), "landlord-safe-indoor-garden-setup"),
    (("quiet", "studio", "noise", "silent"), "quiet-countertop-gardens-studios"),
    (("windowsill", "without kit", "soil pot"), "windowsill-herbs-without-kit"),
    (("grow light", "schedule", "timer"), "grow-light-schedules-herbs"),
    (("basil", "first harvest"), "basil-countertop-first-harvest"),
    (("countertop garden", "apartment kit", "best countertop"), "best-countertop-garden-apartments"),
    (("cheap", "under $", "budget"), "cheapest-indoor-herb-garden-apartment"),
    (("electricity", "running cost", "pod cost"), "countertop-garden-running-cost"),
]


def _slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.split("/")[-1] if path else ""


def _map_query_to_slug(query: str) -> str | None:
    low = query.lower()
    for tokens, slug in QUERY_GUIDE_RULES:
        if any(token in low for token in tokens):
            return slug
    return None


def _title_covers_query(title: str, query: str) -> bool:
    t = title.lower()
    q = query.lower()
    if q in t:
        return True
    # Treat brand-order swaps as already covered for vs queries.
    if " vs " in q or " versus " in q:
        parts = re.split(r"\s+(?:vs|versus)\s+", q, maxsplit=1)
        if len(parts) == 2 and all(p.strip() and p.strip() in t for p in parts):
            return True
    tokens = [tok for tok in re.findall(r"[a-z0-9]+", q) if len(tok) > 2]
    if tokens and sum(1 for tok in tokens if tok in t) >= max(2, len(tokens) - 1):
        return True
    return False


def propose_ctr_first_changes(metrics: dict, *, max_items: int = 5) -> list[dict]:
    guides = {g.slug: g for g in load_guides()}
    changes: list[dict] = []
    seen: set[str] = set()

    def add(change: dict) -> None:
        key = f"{change.get('type')}:{change.get('slug')}"
        if key in seen or len(changes) >= max_items:
            return
        seen.add(key)
        changes.append(change)

    queries = sorted(
        (metrics.get("top_queries") or []),
        key=lambda q: (-int(q.get("impressions") or 0), float(q.get("position") or 99)),
    )
    for row in queries:
        if int(row.get("clicks") or 0) > 0:
            continue
        query = (row.get("query") or "").strip()
        impr = int(row.get("impressions") or 0)
        pos = float(row.get("position") or 99)
        # Require a little more signal before auto-rewriting titles.
        if not query or impr < 2 or pos > 80:
            continue
        slug = _map_query_to_slug(query)
        if not slug or slug not in guides:
            continue
        guide = guides[slug]
        title = guide.title
        if _title_covers_query(title, query):
            # Already matched — only suggest description polish when missing.
            if query.lower() not in guide.description.lower() and impr >= 3:
                add(
                    {
                        "type": "tune_guide_seo",
                        "slug": slug,
                        "description_patch": f"{query} for apartments — clear picks, noise, light, and refill cost."[:160],
                        "reason": f"CTR-first query desc: {impr} impr, pos {pos:.1f}, 0 clicks",
                        "query": query,
                        "auto_safe": True,
                    }
                )
            continue
        phrase = query.strip()
        year_bit = " (2026)" if "2026" not in title else ""
        if "vs" in phrase.lower():
            new_title = f"{phrase.title()}{year_bit} — which is better?"[:70]
        else:
            new_title = f"{phrase[:1].upper()}{phrase[1:]}{year_bit} — apartment guide"[:70]
        add(
            {
                "type": "tune_guide_seo",
                "slug": slug,
                "title_patch": new_title,
                "description_patch": (
                    guide.description
                    if phrase.lower() in guide.description.lower()
                    else f"{phrase} for apartments — clear picks, noise, light, and refill cost."[:160]
                ),
                "reason": f"CTR-first query: {impr} impr, pos {pos:.1f}, 0 clicks",
                "query": query,
                "auto_safe": impr >= 5,
            }
        )

    pages = metrics.get("top_pages") or metrics.get("top_landing_pages") or []
    for row in pages:
        if int(row.get("clicks") or 0) > 0:
            continue
        impr = int(row.get("impressions") or 0)
        if impr < 3:
            continue
        slug = _slug_from_url(row.get("page") or row.get("path") or "")
        if not slug or slug not in guides:
            continue
        guide = guides[slug]
        title = guide.title
        if "2026" not in title:
            add(
                {
                    "type": "tune_guide_seo",
                    "slug": slug,
                    "title_patch": f"{title} (2026)"[:70],
                    "reason": f"CTR-first page: {impr} impr, 0 clicks",
                    "auto_safe": True,
                }
            )

    return changes
