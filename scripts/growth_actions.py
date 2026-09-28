#!/usr/bin/env python3
"""High-impact growth helpers — distribution packs, summaries, IndexNow."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_json, now_utc, save_json, site_url
from guide_content import load_guides

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "products" / "growth" / "distribution"
SUMMARIES_DIR = ROOT / "products" / "growth" / "daily-summaries"
LATEST = ROOT / "products" / "analytics" / "latest.json"
PLAYBOOK = ROOT / "products" / "analytics" / "working-playbook.json"

KIT_TARGETS = [
    {
        "slug": "kits-studio-silence",
        "title": "Studio Silence Kit — quiet apartment herb garden",
        "url": "https://sillgarden.com/kits/studio-silence/",
        "description": "No-pump kit + tray + shade for studios that sleep in the same room.",
        "lane": "studio",
    },
    {
        "slug": "kits-kitchen-capacity",
        "title": "Kitchen Capacity Kit — AeroGarden Harvest stack",
        "url": "https://sillgarden.com/kits/kitchen-capacity/",
        "description": "Harvest-class + blanks/seeds so month two does not empty the wallet.",
        "lane": "kitchen",
    },
    {
        "slug": "kits-under-50",
        "title": "Under-$50 apartment sill herb kit",
        "url": "https://sillgarden.com/kits/under-50/",
        "description": "Pots, tray, mix, seeds, clip light — renter-safe start.",
        "lane": "budget",
    },
]


def ping_indexnow() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "submit_indexing.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    ok = proc.returncode == 0 and "IndexNow OK" in ((proc.stdout or "") + (proc.stderr or ""))
    return {
        "ok": ok,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-500:],
        "stderr": (proc.stderr or "")[-500:],
    }


def pick_distribution_target(metrics: dict | None = None) -> dict | None:
    metrics = metrics or {}
    guides = load_guides()
    if not guides:
        return None
    by_slug = {g.slug: g for g in guides}
    # Prefer exact demand pages over fuzzy slug matching.
    query_prefer = [
        (("bounty vs harvest", "harvest vs bounty", "bounty vs bounty"), "compare-aerogarden-models"),
        (("aerogarden vs click", "click and grow vs aerogarden", "click & grow vs"), "aerogarden-vs-click-and-grow"),
        (("farm vs farm plus",), "compare-aerogarden-models"),
    ]
    top = (metrics.get("top_queries") or [])[:8]
    for q in top:
        query = (q.get("query") or "").lower()
        for needles, slug in query_prefer:
            if any(n in query for n in needles) and slug in by_slug:
                g = by_slug[slug]
                return {
                    "slug": g.slug,
                    "title": g.title,
                    "url": g.url,
                    "description": g.description,
                    "reason": f"matches query “{q.get('query')}”",
                }
    featured = [g for g in guides if g.frontmatter.get("featured")]
    pool = featured or guides
    for q in top:
        query = (q.get("query") or "").lower()
        for g in pool:
            tokens = g.slug.replace("-", " ")
            if any(tok and tok in query for tok in tokens.split()):
                return {
                    "slug": g.slug,
                    "title": g.title,
                    "url": g.url,
                    "description": g.description,
                    "reason": f"matches query “{q.get('query')}”",
                }
    g = sorted(pool, key=lambda d: str(d.frontmatter.get("pubDate") or ""), reverse=True)[0]
    return {
        "slug": g.slug,
        "title": g.title,
        "url": g.url,
        "description": g.description,
        "reason": "newest/featured guide",
    }


def _sessions_7d(metrics: dict | None) -> int:
    hero = (metrics or {}).get("hero") or {}
    try:
        return int(hero.get("sessions_7d") or 0)
    except (TypeError, ValueError):
        return 0


def _kit_for_query(query: str) -> dict:
    q = query.lower()
    if any(x in q for x in ("quiet", "noise", "studio", "click and grow", "click & grow")):
        return KIT_TARGETS[0]
    if any(x in q for x in ("under 50", "cheap", "budget", "$50")):
        return KIT_TARGETS[2]
    if any(x in q for x in ("bounty", "harvest", "aerogarden", "capacity")):
        return KIT_TARGETS[1]
    return KIT_TARGETS[0]


def build_distribution_pack(metrics: dict | None = None) -> dict:
    """Kit-first packs when traffic is flat; otherwise guide + matching kit stack."""
    metrics = metrics or {}
    base = site_url().rstrip("/")
    sessions = _sessions_7d(metrics)
    playbook = load_json(PLAYBOOK, {}) or {}
    money_urls = playbook.get("money_urls") or [k["url"] for k in KIT_TARGETS]
    guide = pick_distribution_target(metrics)
    top_q = ((metrics.get("top_queries") or [{}])[0].get("query") or "")
    kit = _kit_for_query(top_q)
    picker = f"{base}/tools/kit-picker/"
    year_cost = f"{base}/tools/year-one-cost/"
    kits_hub = f"{base}/kits/"
    disclosure = f"{base}/disclosure/"

    # Flat traffic → lead with physical stacks (lesson 2026-09-28).
    if sessions <= 2 or not guide:
        target = {
            "slug": kit["slug"],
            "title": kit["title"],
            "url": kit["url"],
            "description": kit["description"],
            "reason": "kit-first while sessions_7d is flat",
            "kind": "kit",
        }
    else:
        target = {**guide, "kind": "guide", "kit_url": kit["url"]}

    title = target["title"]
    url = target["url"]
    desc = target["description"]
    reddit_body = (
        "I put together apartment-focused kit stacks (noise, footprint, refill cost — not brand ads) "
        "so you’re not guessing accessories.\n\n"
        f"**Lane:** {desc}\n\n"
        f"Buy stack: {kit['url']}\n"
        f"60-second picker: {picker}\n"
        f"Year-one cost: {year_cost}\n"
    )
    if guide and target.get("kind") == "guide":
        reddit_body += f"Matching guide: {guide['url']}\n"
    reddit_body += f"\nDisclosure: {disclosure}\n\nCurious what people kept plugged in after month two."

    pack = {
        "generated_at": now_utc(),
        "target": target,
        "kit": kit,
        "money_urls": money_urls,
        "priority": "P0_kit_first" if sessions <= 2 else "P1_guide_plus_kit",
        "lessons_ref": "products/growth/AGENT-LESSONS.md",
        "channels": {
            "x": (
                f"Studio vs kitchen herb kit — physical stacks:\n"
                f"{kits_hub}\n{picker}\n\n#IndoorGarden #ApartmentLiving"
            ),
            "bluesky": f"{title}\n\n{desc}\n\n{url}\nPicker: {picker}",
            "mastodon": f"{title}\n\n{url}\n\n#IndoorGarden #ApartmentLiving #Herbs",
            "reddit": (
                f"Sub: r/Apartmentliving (alt: r/hydroponics, r/gardening)\n"
                f"Title: AeroGarden vs Click & Grow for a small apartment — which would you buy first?\n\n"
                f"Body:\n{reddit_body}"
            ),
            "pinterest": (
                f"Pin title: {kit['title']}\n"
                f"Description: {kit['description']} Physical stack, not a PDF.\n"
                f"Link: {kit['url']}?utm_source=pinterest&utm_medium=social&utm_campaign=growth-agent\n"
                f"Disclosure: {disclosure}"
            ),
            "youtube_pin": (
                "Apartment kit pick (noise vs capacity) + year-one cost:\n"
                f"{picker}\n{kits_hub}\n{year_cost}"
            ),
            "devto": f"Syndicate canonical: {guide['url'] if guide else kits_hub}",
        },
        "checklist": [
            "Post Reddit draft today (kit stacks first, disclose affiliates)",
            "Create 1–3 Pinterest pins to /kits/* (not guide-only)",
            "Pin kit comment on top YouTube Shorts (or run youtube_post_kit_comments.py)",
            "If new money URLs shipped: update GSC P0 list + nudge_google_indexing PRIORITY",
        ],
        "distribution_rules": playbook.get("distribution_rules") or [],
    }
    return pack


def save_distribution_pack(pack: dict) -> Path:
    day = now_utc()[:10]
    path = DIST_DIR / f"{day}.json"
    save_json(path, pack)
    save_json(DIST_DIR / "latest.json", pack)
    _write_kit_paste_files(pack, day)
    _write_gsc_money_list(pack)
    return path


def _write_gsc_money_list(pack: dict) -> None:
    urls = pack.get("money_urls") or [k["url"] for k in KIT_TARGETS]
    lines = [
        "# GSC — Request indexing (paste these)",
        "",
        "In Google Search Console → URL inspection → paste URL → **Request indexing**.",
        "",
        "Do the P0 list first (quota is limited). Maintained by growth agent from working-playbook money_urls.",
        "",
        "## P0 — money URLs",
        "",
        "```",
        *urls,
        "```",
        "",
        "Sitemap: `https://sillgarden.com/sitemap-index.xml`",
        "",
        f"_Generated {now_utc()}_",
        "",
    ]
    (DIST_DIR / "gsc-request-indexing-urls.md").write_text("\n".join(lines), encoding="utf-8")


def _write_kit_paste_files(pack: dict, day: str) -> None:
    kit = pack.get("kit") or KIT_TARGETS[0]
    channels = pack.get("channels") or {}
    reddit = channels.get("reddit") or ""
    pin = channels.get("pinterest") or ""
    yt = channels.get("youtube_pin") or ""
    (DIST_DIR / f"reddit-ready-{day}.md").write_text(
        f"# Paste-ready Reddit — kit-first ({day})\n\n{reddit}\n",
        encoding="utf-8",
    )
    (DIST_DIR / f"pinterest-ready-{day}.md").write_text(
        f"# Pinterest — kit-first ({day})\n\n{pin}\n\nAlso pin: "
        + ", ".join(k["url"] for k in KIT_TARGETS)
        + "\n",
        encoding="utf-8",
    )
    (DIST_DIR / f"manual-acquisition-{day}.md").write_text(
        "\n".join(
            [
                f"# Manual acquisition — {day}",
                "",
                "1. GSC P0: `gsc-request-indexing-urls.md`",
                "2. Reddit: kit-first draft in `reddit-ready-*.md`",
                "3. Pinterest: kit pins",
                "4. YouTube pin comment:",
                "",
                "```",
                yt,
                "```",
                "",
                f"Primary kit lane today: {kit.get('title')} → {kit.get('url')}",
                "",
                "Rules: products/growth/AGENT-LESSONS.md",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_daily_summary(payload: dict) -> Path:
    day = now_utc()[:10]
    path = SUMMARIES_DIR / f"{day}.md"
    lines = [
        f"# Sill Garden growth summary — {day}",
        "",
        f"Generated: {payload.get('generated_at') or now_utc()}",
        "",
        "## Applied",
    ]
    applied = payload.get("applied") or []
    if applied:
        lines.extend(f"- {item}" for item in applied)
    else:
        lines.append("- None")
    lines.extend(["", "## Proposed / manual"])
    proposed = payload.get("proposed") or []
    if proposed:
        for item in proposed:
            lines.append(f"- {item.get('title') or item.get('type')}: {item.get('detail') or item.get('reason')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Learnings"])
    for item in payload.get("learnings") or []:
        lines.append(f"- {item}")
    health = payload.get("outcome_health") or {}
    if health:
        lines.extend(
            [
                "",
                "## Outcome health",
                f"- Severity: {health.get('severity')}",
                f"- Zero-session days: {health.get('zero_session_day_count')}",
            ]
        )
        for reason in health.get("reasons") or []:
            lines.append(f"- {reason}")
        for action in health.get("actions") or []:
            lines.append(f"- TODO: {action}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def metrics_from_latest() -> dict:
    latest = load_json(LATEST, {}) or {}
    gsc = (latest.get("sources") or {}).get("gsc") or {}
    return {
        "top_queries": gsc.get("top_queries") or [],
        "top_pages": gsc.get("top_pages") or [],
        "impressions": gsc.get("impressions") or 0,
        "clicks": gsc.get("clicks") or 0,
        "hero": latest.get("hero") or {},
    }
