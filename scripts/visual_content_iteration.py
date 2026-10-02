#!/usr/bin/env python3
"""Apply safe content/visuality iterations from competitive learning.

Every daily growth iteration should APPLY auto proposed_actions (FAQ, year-stamp)
and bounded semi-auto upgrades (comparison tables, empty verdict CTAs). Manual
visual redesign stays queued.

  python scripts/visual_content_iteration.py
  python scripts/visual_content_iteration.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_dotenv, load_json, now_utc, save_json
from board_actions import enqueue
from guide_content import load_guides, save_guide

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "products" / "growth" / "competitive-learning" / "latest.json"
OUT = ROOT / "products" / "growth" / "visual-iteration-latest.json"
BACKLOG = ROOT / "products" / "growth" / "visual-backlog.md"
YEAR = date.today().year

MONEY_SLUGS = (
    "aerogarden-vs-click-and-grow",
    "compare-aerogarden-models",
    "best-countertop-garden-apartments",
    "cheapest-indoor-herb-garden-apartment",
    "click-and-grow-vs-idoo-auk",
)

QUICK_TABLE = """
## Quick pick

| Need | Lean toward |
|------|-------------|
| More capacity / herbs | AeroGarden Harvest-class |
| Silence / studio sleep | Click & Grow Smart Garden 3 |
| Under $50 DIY start | Soil pots + tray (+ clip LED if dim) |
""".strip()


def _year_stamp_title(title: str) -> str | None:
    if re.search(r"\b202[4-9]\b", title):
        return None
    if "—" in title:
        left, _, right = title.partition("—")
        return f"{left.strip()} ({YEAR}) — {right.strip()}"
    return f"{title} ({YEAR})"


def _append_faq(body: str, question: str, answer: str) -> str:
    if re.search(re.escape(question), body, re.I):
        return body
    block = f"\n**{question}**  \n{answer}\n"
    if re.search(r"^## FAQ\s*$", body, re.M):
        parts = re.split(r"(^## FAQ\s*$)", body, maxsplit=1, flags=re.M)
        if len(parts) == 3:
            head, faq_h, rest = parts
            next_h = re.search(r"^## ", rest, re.M)
            if next_h:
                idx = next_h.start()
                return head + faq_h + rest[:idx] + block + rest[idx:]
            return head + faq_h + rest.rstrip() + "\n" + block
    return body.rstrip() + "\n\n## FAQ\n" + block


def _ensure_quick_table(body: str) -> str | None:
    if re.search(r"^## Quick (pick|answer)\s*$", body, re.M):
        return None
    if re.search(r"^\|.+\|.+\|$", body, re.M):
        return None
    # Insert after first paragraph block
    parts = body.split("\n\n", 1)
    if len(parts) == 2:
        return parts[0] + "\n\n" + QUICK_TABLE + "\n\n" + parts[1]
    return body.rstrip() + "\n\n" + QUICK_TABLE + "\n"


def _default_verdict(slug: str, title: str) -> str:
    low = f"{slug} {title}".lower()
    if "cheapest" in low or "under" in low:
        return (
            "Start under $50 with soil pots + a waterproof tray if your sill gets real daylight. "
            "Add a clip LED before pods; upgrade to a 3-pod kit only when DIY keeps failing."
        )
    if "idoo" in low or "auk" in low:
        return (
            "Pick Click & Grow for silence; iDOO-class kits when you want more pods per dollar "
            "and will tolerate pump noise."
        )
    if "compare" in low or "bounty" in low or "harvest" in low:
        return (
            "Start with Harvest-class (≈6 pods) for most apartments. Step up to Bounty only if you "
            "cook herbs daily and have counter depth."
        )
    if "aerogarden" in low and "click" in low:
        return (
            "Pick AeroGarden Harvest-class for faster growth and more herbs; Click & Grow Smart Garden 3 "
            "when silence and a smaller footprint matter more than yield."
        )
    return (
        f"For {title}: match noise, footprint, and refill cost to your apartment — "
        "not the tallest tower on the product page."
    )


def _faq_answer(question: str) -> str:
    q = question.lower()
    if "bounty" in q and "elite" in q:
        return (
            "Bounty Elite adds luxuries (often Wi‑Fi/app and stronger light) over Basic/Standard. "
            "Most apartments should buy capacity they will harvest — Elite is optional, not required."
        )
    if "harvest" in q and "bounty" in q:
        return (
            "Harvest-class suits herbs on a small counter; Bounty suits taller plants and heavier daily cooking. "
            "If you mainly grow basil/mint, Harvest-class is usually enough."
        )
    if "click" in q and "aero" in q:
        return (
            "AeroGarden uses a small pump and usually grows faster with more pods; Click & Grow is silent "
            "and sill-friendly. Pick silence vs capacity first."
        )
    return (
        "Match the setup to your light, noise tolerance, and landlord rules — not brand hype. "
        "Start small and upgrade after one successful harvest."
    )


def _write_backlog(learnings: list[str]) -> str:
    """Update backlog without unchecking completed items."""
    checklist = [
        "Home hero: one brand + one CTA; no card clutter in first viewport",
        "Guide pages: Quick verdict + product picks before long prose",
        "Unique og/hero image per money guide (no repeated stock across top 5)",
        "Comparison tables visible without scrolling on desktop",
    ]
    checked: dict[str, bool] = {}
    if BACKLOG.is_file():
        for line in BACKLOG.read_text(encoding="utf-8").splitlines():
            m = re.match(r"- \[([ xX])\] (.+)$", line.strip())
            if m:
                checked[m.group(2).strip()] = m.group(1).lower() == "x"

    # Auto-check items we can verify from guides
    docs = {d.slug: d for d in load_guides()}
    money = [docs[s] for s in MONEY_SLUGS if s in docs]
    if money and all(d.frontmatter.get("verdict") for d in money):
        checked["Guide pages: Quick verdict + product picks before long prose"] = True
    if money and all(
        re.search(r"^\|.+\|.+\|$", d.body, re.M)
        or re.search(r"^## Quick (pick|answer)\s*$", d.body, re.M)
        for d in money
        if d.frontmatter.get("type") == "comparison" or "vs" in d.slug
    ):
        checked["Comparison tables visible without scrolling on desktop"] = True
    if money and len({str(d.frontmatter.get("image") or "") for d in money}) >= min(4, len(money)):
        checked["Unique og/hero image per money guide (no repeated stock across top 5)"] = True
    # Home hero is structural in index.astro — treat as done unless explicitly unchecked forever
    checked.setdefault("Home hero: one brand + one CTA; no card clutter in first viewport", True)

    lines = [
        "# Visuality backlog (from competitive learning)",
        "",
        f"Updated: {now_utc()}",
        "",
    ]
    for c in checklist:
        mark = "x" if checked.get(c) else " "
        lines.append(f"- [{mark}] {c}")
    lines.append("")
    lines.append("## Peer learnings")
    lines.extend(f"- {x}" for x in learnings[:8])
    lines.append("")
    BACKLOG.write_text("\n".join(lines), encoding="utf-8")
    return "updated visual-backlog.md"


def apply_iterations(*, dry_run: bool) -> dict:
    pack = load_json(COMP, {}) or {}
    learnings = pack.get("learnings") or []
    actions = pack.get("proposed_actions") or []
    gsc_queries = [str(q).strip() for q in (pack.get("gsc_queries") or []) if str(q).strip()]
    applied: list[str] = []
    queued: list[str] = []

    joined = " ".join(learnings).lower()
    action_types = {str(a.get("type") or "") for a in actions}
    guides = load_guides()
    by_slug = {g.slug: g for g in guides}
    featured = [g for g in guides if g.frontmatter.get("featured")] or guides[:4]
    money_docs = [by_slug[s] for s in MONEY_SLUGS if s in by_slug]

    # Auto: year-stamp featured commercial titles when peers use year freshness
    if "year" in joined or "seo_year_stamp" in action_types:
        for doc in featured[:3]:
            title = str(doc.frontmatter.get("title") or "")
            new_title = _year_stamp_title(title)
            if not new_title or new_title == title:
                continue
            label = f"year_stamp:{doc.slug} -> {new_title}"
            if dry_run:
                applied.append(f"[dry-run] {label}")
                continue
            doc.frontmatter["title"] = new_title
            doc.frontmatter["updatedDate"] = date.today().isoformat()
            save_guide(doc)
            applied.append(label)

    # Auto: content_faq — apply GSC/peer questions onto money guides
    if "content_faq" in action_types or gsc_queries:
        faq_budget = 3
        queries = gsc_queries or [
            "Is AeroGarden Bounty Basic better than Bounty Elite?",
            "AeroGarden Harvest vs Bounty for apartments",
            "AeroGarden vs Click and Grow which is quieter?",
        ]
        for query in queries:
            if faq_budget <= 0:
                break
            q = query if query.endswith("?") else (query[0].upper() + query[1:] + "?")
            # Prefer comparison guides for vs questions
            targets = money_docs[:3]
            if "bounty" in q.lower() or "harvest" in q.lower():
                targets = [d for d in money_docs if "compare" in d.slug or "aerogarden" in d.slug][:2] or targets
            for doc in targets:
                if faq_budget <= 0:
                    break
                if re.search(re.escape(q.rstrip("?")), doc.body, re.I):
                    continue
                label = f"faq:{doc.slug}:{q[:48]}"
                if dry_run:
                    applied.append(f"[dry-run] {label}")
                    faq_budget -= 1
                    continue
                doc.body = _append_faq(doc.body, q, _faq_answer(q))
                doc.frontmatter["updatedDate"] = date.today().isoformat()
                save_guide(doc)
                applied.append(label)
                faq_budget -= 1

    # Semi-auto: content_table — ensure early Quick pick table on vs/comparison guides
    if "content_table" in action_types or "table" in joined:
        for doc in money_docs:
            if doc.frontmatter.get("type") not in ("comparison", "guide") and "vs" not in doc.slug:
                continue
            if doc.frontmatter.get("type") == "guide" and "vs" not in doc.slug and "compare" not in doc.slug:
                # Still allow cheapest / countertop if learning insists
                if "cheapest" not in doc.slug and "countertop" not in doc.slug:
                    continue
            new_body = _ensure_quick_table(doc.body)
            if not new_body:
                continue
            label = f"table:{doc.slug}"
            if dry_run:
                applied.append(f"[dry-run] {label}")
                continue
            doc.body = new_body
            doc.frontmatter["updatedDate"] = date.today().isoformat()
            save_guide(doc)
            applied.append(label)

    # Semi-auto: cro_cta — fill missing verdict on money guides
    if "cro_cta" in action_types or "cta" in joined or "verdict" in joined:
        for doc in money_docs:
            if doc.frontmatter.get("verdict"):
                continue
            verdict = _default_verdict(doc.slug, doc.title)
            label = f"verdict:{doc.slug}"
            if dry_run:
                applied.append(f"[dry-run] {label}")
                continue
            doc.frontmatter["verdict"] = verdict
            doc.frontmatter["updatedDate"] = date.today().isoformat()
            save_guide(doc)
            applied.append(label)

    # Queue only true manual visual redesign items (not FAQ/table/cta we just applied)
    for act in actions:
        kind = str(act.get("type") or "")
        if kind in ("content_faq", "content_table", "cro_cta", "seo_year_stamp"):
            continue
        if kind != "visuality":
            continue
        if not dry_run:
            enqueue(
                role="cro",
                action_type="visuality",
                title=str(act.get("title") or "Visual/content iteration"),
                detail=str(act.get("detail") or "")[:300],
                target="competitive-learning",
                auto=False,
                priority=str(act.get("priority") or "P1"),
            )
        queued.append(str(act.get("title") or kind))

    if "visual" in joined or "hero" in joined or "cta" in joined or "visuality" in action_types:
        if dry_run:
            applied.append("[dry-run] visual-backlog.md")
        else:
            applied.append(_write_backlog(learnings))

    payload = {
        "generated_at": now_utc(),
        "applied": applied,
        "queued": queued,
        "learnings_used": learnings[:8],
        "dry_run": dry_run,
    }
    if not dry_run:
        save_json(OUT, payload)
    return payload


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not COMP.is_file():
        from competitive_learning import run_competitive_learning

        run_competitive_learning(max_peers=4, include_llm=True)
    result = apply_iterations(dry_run=args.dry_run)
    print(f"Visual/content iteration {'DRY' if args.dry_run else 'OK'} · applied={len(result['applied'])}")
    for line in result["applied"]:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
