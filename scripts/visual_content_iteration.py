#!/usr/bin/env python3
"""Apply safe content/visuality iterations from competitive learning.

Auto-applies low-risk guide upgrades; enqueues manual visual work.

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
YEAR = date.today().year


def _year_stamp_title(title: str) -> str | None:
    if re.search(r"\b202[4-9]\b", title):
        return None
    if "—" in title:
        left, _, right = title.partition("—")
        return f"{left.strip()} ({YEAR}) — {right.strip()}"
    return f"{title} ({YEAR})"


def apply_iterations(*, dry_run: bool) -> dict:
    pack = load_json(COMP, {}) or {}
    learnings = pack.get("learnings") or []
    actions = pack.get("proposed_actions") or []
    applied: list[str] = []
    queued: list[str] = []

    joined = " ".join(learnings).lower()
    guides = load_guides()
    featured = [g for g in guides if g.frontmatter.get("featured")] or guides[:4]

    # Auto: year-stamp featured commercial titles when peers use year freshness
    if "year" in joined or any(a.get("type") == "seo_year_stamp" for a in actions):
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

    # Queue visuality / CRO items for human or later agent
    for act in actions:
        if act.get("auto"):
            continue
        if not dry_run:
            enqueue(
                role="cro" if act.get("type") in ("visuality", "cro_cta") else "content",
                action_type=str(act.get("type") or "visuality"),
                title=str(act.get("title") or "Visual/content iteration"),
                detail=str(act.get("detail") or "")[:300],
                target="competitive-learning",
                auto=False,
                priority=str(act.get("priority") or "P1"),
            )
        queued.append(str(act.get("title") or act.get("type")))

    # Always leave a concrete visual checklist when peers emphasize hero/CTA
    if "visual" in joined or "hero" in joined or "cta" in joined:
        checklist = [
            "Home hero: one brand + one CTA; no card clutter in first viewport",
            "Guide pages: Quick verdict + product picks before long prose",
            "Unique og/hero image per money guide (no repeated stock across top 5)",
            "Comparison tables visible without scrolling on desktop",
        ]
        if not dry_run:
            path = ROOT / "products" / "growth" / "visual-backlog.md"
            path.write_text(
                "# Visuality backlog (from competitive learning)\n\n"
                f"Updated: {now_utc()}\n\n"
                + "\n".join(f"- [ ] {c}" for c in checklist)
                + "\n\n## Peer learnings\n"
                + "\n".join(f"- {x}" for x in learnings[:8])
                + "\n",
                encoding="utf-8",
            )
            applied.append("wrote visual-backlog.md")

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
    # Ensure competitive pack exists
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
