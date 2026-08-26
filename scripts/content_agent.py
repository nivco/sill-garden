#!/usr/bin/env python3
"""Content agent for Sill Garden — research → refresh + new guides.

Uses GSC/GA4 demand, guide inventory, CONTENT-PIPELINE outlines, optional
LLM web research, and light network probes.

  python scripts/content_agent.py --dry-run
  python scripts/content_agent.py --refresh
  python scripts/content_agent.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_dotenv, load_json, save_json
from growth_actions import metrics_from_latest, ping_indexnow
from guide_content import dump_frontmatter, load_guides, save_guide

ROOT = Path(__file__).resolve().parents[1]
GUIDES_DIR = ROOT / "src" / "content" / "guides"
LATEST = ROOT / "products" / "analytics" / "latest.json"
OUT_DIR = ROOT / "products" / "growth" / "content-agent"
STATE_PATH = OUT_DIR / "state.json"
YEAR = date.today().year

MAX_FAQ_REFRESH = 3
MAX_SEO_REFRESH = 2
MAX_NEW_GUIDES = 1

# Query → existing slug for FAQ / SEO refresh
QUERY_GUIDE_RULES: list[tuple[tuple[str, ...], str]] = [
    (("aerogarden vs", "click and grow vs", "aerogarden comparison", "compare aerogarden"), "aerogarden-vs-click-and-grow"),
    (("countertop garden", "counter top garden"), "best-countertop-garden-apartments"),
    (("low light", "north facing"), "best-low-light-herbs-apartment"),
    (("cheap", "under $50", "budget"), "cheapest-indoor-herb-garden-apartment"),
    (("electricity", "running cost", "pod cost"), "countertop-garden-running-cost"),
    (("quiet", "studio", "noise"), "quiet-countertop-gardens-studios"),
    (("landlord", "rental"), "landlord-safe-indoor-garden-setup"),
    (("windowsill", "without kit"), "windowsill-herbs-without-kit"),
    (("basil", "first harvest"), "basil-countertop-first-harvest"),
    (("grow light", "schedule"), "grow-light-schedules-herbs"),
]

# New guides the agent can ship when GSC shows demand and the file is missing
NEW_GUIDE_SPECS: list[dict[str, Any]] = [
    {
        "slug": "compare-aerogarden-models",
        "triggers": ("compare aerogarden", "aerogarden comparison", "aerogarden models", "aerogarden harvest vs"),
        "title": f"AeroGarden models compared ({YEAR}) — Harvest vs Bounty vs Farm",
        "description": (
            "Compare AeroGarden Harvest, Bounty, and Farm for apartments — pods, footprint, "
            "noise, and which model fits a countertop vs a serious indoor garden."
        ),
        "cluster": "systems",
        "type": "comparison",
        "featured": False,
        "image": "/images/guide-countertop.jpg",
        "imageAlt": "Indoor countertop herb garden under LED light",
        "verdict": (
            "Start with Harvest-class (≈6 pods) for most apartments. Step up to Bounty only if you "
            "cook herbs daily and have counter depth. Skip Farm-scale towers unless you have floor space."
        ),
        "products": [
            {"name": "AeroGarden Harvest / Harvest Lite", "note": "Best first apartment kit", "asin": "B07CKNWHPQ"},
            {"name": "AeroGarden Bounty", "note": "More pods when you outgrow Harvest", "search": "AeroGarden Bounty"},
            {"name": "Click & Grow Smart Garden 3", "note": "Quieter alternative if pump noise matters", "asin": "B01MRVMKQH", "partner": "click-grow"},
        ],
        "body": """Searching **compare AeroGarden models** usually means: which kit fits a real apartment counter, not a showroom.

![Indoor herb seedlings starting under light](/images/inline-seedlings.jpg)

## Quick pick

| Situation | Model class |
|-----------|-------------|
| First kit / small counter | **Harvest** (≈6 pods) |
| Heavy herb cooking | **Bounty** (more pods + taller light) |
| Floor space + big greens | **Farm** / tower class |
| Studio silence > yield | Consider **Click & Grow** instead |

## Harvest vs Bounty vs Farm

| | Harvest class | Bounty class | Farm / tower |
|--|---------------|--------------|--------------|
| Pods (typical) | ~6 | ~9 | 12–24+ |
| Footprint | Countertop | Deeper counter | Floor / dedicated corner |
| Noise | Low pump hum | Low–medium | More mechanical presence |
| Best for | Apartments | Serious home cooks | Dedicated indoor garden space |
| Watch-out | Outgrow capacity | Needs counter depth | Overkill for most rentals |

![Countertop plant setup for a small kitchen](/images/inline-counter-plant.jpg)

## AeroGarden comparison — decision rules

1. **Counter depth first** — if the unit hangs over the edge, you will hate it by week two.
2. **Pods ≠ meals** — six pods of herbs you eat beats twelve pods of garnish you ignore.
3. **Noise + light bleed** — in studios, a quieter wick garden can beat any AeroGarden model.

## FAQ

**Which AeroGarden is best for apartments?**  
Harvest-class. Enough pods for cooking herbs without dominating the kitchen.

**Is Bounty worth it over Harvest?**  
Only if you already fill six pods every cycle and have the counter depth. Otherwise Harvest wins on footprint.

**AeroGarden vs Click & Grow?**  
See our dedicated [AeroGarden vs Click & Grow](/guides/aerogarden-vs-click-and-grow/) guide — silence vs capacity is the real fork.

> **Key takeaway**
> For apartments, buy the smallest AeroGarden that covers the herbs you actually cook. Capacity vanity is how kits become clutter.

## Related

- [AeroGarden vs Click & Grow](/guides/aerogarden-vs-click-and-grow/)
- [Best countertop gardens for apartments](/guides/best-countertop-garden-apartments/)
- [Quiet countertop gardens for studios](/guides/quiet-countertop-gardens-studios/)
""",
    },
    {
        "slug": "countertop-garden-system-guide",
        "triggers": ("countertop garden system", "counter top garden", "best countertop garden system"),
        "title": f"Countertop garden systems ({YEAR}) — kits vs DIY for apartments",
        "description": (
            "What a countertop garden system actually needs — light, water, tray, and when a kit "
            "beats jars for apartment cooking herbs."
        ),
        "cluster": "systems",
        "type": "guide",
        "featured": False,
        "image": "/images/guide-countertop.jpg",
        "imageAlt": "Compact countertop garden on an apartment kitchen counter",
        "verdict": (
            "A real countertop system is light + water + drip control — not just a pretty pot. "
            "Buy a 3–6 pod kit if you want herbs with almost no learning curve; use jars + clip light if budget and silence come first."
        ),
        "products": [
            {"name": "Click & Grow Smart Garden 3", "note": "Simplest silent system", "asin": "B01MRVMKQH", "partner": "click-grow"},
            {"name": "AeroGarden Harvest", "note": "More pods for kitchen counters", "asin": "B07CKNWHPQ"},
            {"name": "Clip-on LED grow light", "note": "DIY system essential", "search": "LED clip grow light indoor plants"},
        ],
        "body": """A **countertop garden system** is anything that reliably grows edible herbs on a kitchen counter: kit or DIY. The system fails when one piece is missing — usually light or a drip tray.

![Compact countertop plant for small spaces](/images/inline-counter-plant.jpg)

## System checklist

1. **Light** — built-in LED or a clip-on aimed at the canopy  
2. **Water** — reservoir, wick, or careful hand-watering  
3. **Containment** — waterproof tray / boot (landlords notice stains)  
4. **Schedule** — 14–16h light with a dark period for sleep  

## Kit vs DIY

| | Kit (AeroGarden / Click & Grow) | DIY (jars + clip light) |
|--|--------------------------------|-------------------------|
| Setup time | Minutes | An evening |
| Noise | Pump or silent wick | Silent |
| Cost to start | Higher | Lower |
| Learning curve | Very low | Medium |
| Best when | You want herbs this month | You want silence + budget control |

![Indoor grow tray kept tidy](/images/inline-grow-tray.jpg)

## FAQ

**What is a countertop garden system?**  
A compact indoor setup (kit or DIY) with light, water, and a tray so herbs grow on a counter without wrecking the surface.

**Do I need a branded kit?**  
No. Kits win on convenience. Jars + a decent clip light win on cost and silence.

**Where should it sit?**  
Stable counter away from bed glare; see [quiet studio tips](/guides/quiet-countertop-gardens-studios/) if you live in one room.

> **Key takeaway**
> Buy a system, not a gadget. Light + water + drip control beat any single “smart” feature.

## Related

- [Best countertop gardens for apartments](/guides/best-countertop-garden-apartments/)
- [Cheapest indoor herb garden](/guides/cheapest-indoor-herb-garden-apartment/)
- [Landlord-safe setup](/guides/landlord-safe-indoor-garden-setup/)
""",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def map_query_to_guide(query: str) -> str | None:
    q = query.lower()
    for keywords, slug in QUERY_GUIDE_RULES:
        if any(k in q for k in keywords):
            return slug
    return None


def _optional_llm_research(query: str) -> str | None:
    prompt = (
        f"Research for an apartment indoor-garden guide (2026). Query: {query}. "
        "Return 3 short factual bullets on noise, cost, and apartment fit. No fluff."
    )
    try:
        key = (os.environ.get("PERPLEXITY_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
        if not key:
            return None
        # Prefer shared helper if Sill has ai_growth_agent
        ai_path = ROOT / "scripts" / "ai_growth_agent.py"
        if ai_path.is_file():
            from ai_growth_agent import _openai_chat, _perplexity_chat

            if os.environ.get("PERPLEXITY_API_KEY", "").strip():
                return (_perplexity_chat(prompt, os.environ["PERPLEXITY_API_KEY"].strip()) or "")[:900]
            return (_openai_chat(prompt, os.environ["OPENAI_API_KEY"].strip()) or "")[:900]
    except Exception as exc:  # noqa: BLE001
        return f"(research skipped: {exc})"[:200]
    return None


def _probe_public_page(url: str) -> dict[str, Any]:
    import urllib.request

    out: dict[str, Any] = {"url": url, "ok": False}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SillContentAgent/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read(60_000).decode("utf-8", errors="replace")
            out["ok"] = True
            out["status"] = getattr(resp, "status", 200)
            out["mentions_year"] = str(YEAR) in body
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:160]
    return out


def research(metrics: dict) -> dict:
    queries = metrics.get("top_queries") or []
    zero_click = [
        q
        for q in queries
        if int(q.get("impressions") or 0) >= 1 and int(q.get("clicks") or 0) == 0
    ]
    docs = load_guides()
    network = [
        _probe_public_page("https://sillgarden.com/llms.txt"),
        _probe_public_page("https://sillgarden.com/guides/aerogarden-vs-click-and-grow/"),
        _probe_public_page("https://www.aerogarden.com/"),
    ]
    llm_notes: dict[str, str] = {}
    for q in zero_click[:3]:
        query = (q.get("query") or "").strip()
        if query:
            note = _optional_llm_research(query)
            if note:
                llm_notes[query] = note
    return {
        "generated": now_utc(),
        "zero_click_queries": zero_click[:15],
        "network_probes": network,
        "llm_notes": llm_notes,
        "guide_count": len(docs),
        "existing_slugs": [d.slug for d in docs],
    }


def _faq_exists(body: str, question: str) -> bool:
    return question.lower().rstrip("?") in body.lower()


def _faq_answer(query: str) -> str:
    low = query.lower()
    if "aerogarden" in low and "click" in low:
        return (
            "For most kitchens, AeroGarden Harvest-class wins on capacity. "
            "For studios where the unit sits near a bed, Click & Grow usually wins on silence."
        )
    if "aerogarden" in low and ("comparison" in low or "model" in low or "compare" in low):
        return (
            "Start with Harvest-class for apartments. Move to Bounty only if you already fill six pods "
            "and have counter depth. Farm-scale towers are overkill for most rentals."
        )
    if "countertop garden" in low:
        return (
            "A countertop garden needs light, water, and a drip tray. Kits are fastest; jars plus a clip-on "
            "LED are quieter and cheaper if you will maintain them."
        )
    return (
        f"For \"{query}\", match the setup to your light, noise tolerance, and landlord rules — "
        "not brand hype. Start small and upgrade after one successful harvest."
    )


def propose_actions(metrics: dict, research_pack: dict) -> list[dict]:
    docs = {d.slug: d for d in load_guides()}
    actions: list[dict] = []

    # New guides from GSC demand + curated specs
    new_n = 0
    for spec in NEW_GUIDE_SPECS:
        if new_n >= MAX_NEW_GUIDES:
            break
        slug = spec["slug"]
        if slug in docs or (GUIDES_DIR / f"{slug}.md").is_file():
            continue
        triggers = spec["triggers"]
        matched = None
        for q in metrics.get("top_queries") or []:
            query = (q.get("query") or "").lower()
            if any(t in query for t in triggers):
                matched = q
                break
        # Also ship first missing high-value guide even with thin GSC if network shows site is live
        if not matched and new_n == 0 and any(p.get("ok") for p in (research_pack.get("network_probes") or [])):
            # Prefer first trigger-shaped demand among all zero-click, else first missing spec with apartment intent
            for q in research_pack.get("zero_click_queries") or []:
                query = (q.get("query") or "").lower()
                if any(t in query for t in triggers):
                    matched = q
                    break
        if not matched:
            # Still allow one opportunistic new guide when GSC has related head terms
            head = " ".join(
                (q.get("query") or "") for q in (metrics.get("top_queries") or [])[:8]
            ).lower()
            if not any(t in head for t in triggers):
                continue
            matched = {"query": triggers[0], "impressions": 0, "position": "-"}
        actions.append(
            {
                "type": "create_guide",
                "slug": slug,
                "spec": spec,
                "reason": (
                    f"GSC demand for {(matched.get('query') if isinstance(matched, dict) else triggers[0])} "
                    f"— ship new {spec['type']}"
                ),
                "bucket": "new",
            }
        )
        new_n += 1

    # FAQ refresh on existing guides
    faq_n = 0
    for q in metrics.get("top_queries") or []:
        if faq_n >= MAX_FAQ_REFRESH:
            break
        if int(q.get("clicks") or 0) > 0:
            continue
        query = (q.get("query") or "").strip()
        slug = map_query_to_guide(query)
        if not slug or slug not in docs:
            continue
        doc = docs[slug]
        question = query[0].upper() + query[1:]
        if not question.endswith("?"):
            question += "?"
        if _faq_exists(doc.body, question):
            continue
        actions.append(
            {
                "type": "add_faq",
                "slug": slug,
                "question": question,
                "answer": _faq_answer(query),
                "reason": f"GSC zero-click: {q.get('impressions')} impr, pos {q.get('position')}",
                "bucket": "refresh",
            }
        )
        faq_n += 1

    # Title year / description refresh
    seo_n = 0
    for q in metrics.get("top_queries") or []:
        if seo_n >= MAX_SEO_REFRESH:
            break
        query = (q.get("query") or "").strip()
        slug = map_query_to_guide(query)
        if not slug or slug not in docs:
            continue
        doc = docs[slug]
        title = str(doc.frontmatter.get("title") or "")
        if str(YEAR) in title and query.lower().split()[0] in title.lower():
            continue
        # Light polish: ensure year + primary phrase presence
        new_title = title
        if str(YEAR) not in new_title:
            new_title = re.sub(r"\b20\d{2}\b", str(YEAR), new_title)
            if str(YEAR) not in new_title:
                new_title = f"{new_title.rstrip()} ({YEAR})"
        words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 3]
        if words and sum(1 for w in words if w in new_title.lower()) < min(2, len(words)):
            # Keep existing title if already long; only bump description
            desc = str(doc.frontmatter.get("description") or "")
            if query.lower() not in desc.lower():
                new_desc = f"{query[0].upper() + query[1:]} — {desc}"[:160]
                actions.append(
                    {
                        "type": "tune_guide_seo",
                        "slug": slug,
                        "title": None,
                        "description": new_desc,
                        "reason": f"Content agent: weave GSC query into meta — {query}",
                        "bucket": "refresh",
                    }
                )
                seo_n += 1
            continue
        if new_title != title:
            actions.append(
                {
                    "type": "tune_guide_seo",
                    "slug": slug,
                    "title": new_title[:70],
                    "description": None,
                    "reason": f"Content agent: year stamp {YEAR}",
                    "bucket": "refresh",
                }
            )
            seo_n += 1

    return actions


def _append_faq(body: str, question: str, answer: str) -> str:
    block = f"\n**{question}**  \n{answer}\n"
    if re.search(r"^## FAQ\s*$", body, re.M):
        # Insert before next ## after FAQ or at end of FAQ section
        parts = re.split(r"(^## FAQ\s*$)", body, maxsplit=1, flags=re.M)
        if len(parts) == 3:
            head, faq_h, rest = parts
            # rest starts after ## FAQ line
            next_h = re.search(r"^## ", rest, re.M)
            if next_h:
                idx = next_h.start()
                return head + faq_h + rest[:idx] + block + rest[idx:]
            return head + faq_h + rest.rstrip() + "\n" + block
    # Append FAQ section
    return body.rstrip() + "\n\n## FAQ\n" + block


def apply_actions(actions: list[dict], *, dry_run: bool) -> list[dict]:
    applied: list[dict] = []
    docs = {d.slug: d for d in load_guides()}

    for act in actions:
        kind = act.get("type")
        if dry_run:
            applied.append({**act, "status": "dry-run"})
            continue

        if kind == "create_guide":
            spec = act.get("spec") or {}
            slug = act.get("slug") or spec.get("slug")
            path = GUIDES_DIR / f"{slug}.md"
            if path.is_file():
                applied.append({**act, "status": "skipped", "detail": "exists"})
                continue
            meta = {
                "title": spec["title"],
                "description": spec["description"],
                "pubDate": date.today().isoformat(),
                "updatedDate": date.today().isoformat(),
                "cluster": spec.get("cluster", "systems"),
                "type": spec.get("type", "guide"),
                "featured": bool(spec.get("featured")),
                "image": spec.get("image", "/images/guide-countertop.jpg"),
                "imageAlt": spec.get("imageAlt", "Indoor plants"),
                "verdict": spec.get("verdict", ""),
                "products": spec.get("products") or [],
            }
            path.write_text(dump_frontmatter(meta) + (spec.get("body") or "").lstrip("\n"), encoding="utf-8")
            applied.append({**act, "status": "applied"})

        elif kind == "add_faq":
            slug = act.get("slug")
            doc = docs.get(slug)
            if not doc:
                applied.append({**act, "status": "skipped", "detail": "missing guide"})
                continue
            q = act.get("question") or ""
            if _faq_exists(doc.body, q):
                applied.append({**act, "status": "skipped", "detail": "faq exists"})
                continue
            doc.body = _append_faq(doc.body, q, act.get("answer") or "")
            doc.frontmatter["updatedDate"] = date.today().isoformat()
            save_guide(doc)
            applied.append({**act, "status": "applied"})

        elif kind == "tune_guide_seo":
            slug = act.get("slug")
            doc = docs.get(slug)
            if not doc:
                applied.append({**act, "status": "skipped", "detail": "missing guide"})
                continue
            changed = False
            if act.get("title") and act["title"] != doc.frontmatter.get("title"):
                doc.frontmatter["title"] = act["title"]
                changed = True
            if act.get("description") and act["description"] != doc.frontmatter.get("description"):
                doc.frontmatter["description"] = act["description"]
                changed = True
            if changed:
                doc.frontmatter["updatedDate"] = date.today().isoformat()
                save_guide(doc)
                applied.append({**act, "status": "applied"})
            else:
                applied.append({**act, "status": "skipped", "detail": "unchanged"})
        else:
            applied.append({**act, "status": "skipped", "detail": f"unknown {kind}"})

    return applied


def refresh_analytics() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "analytics_summary.py")],
        cwd=str(ROOT),
        check=False,
    )


def summarize(research_pack: dict, applied: list[dict]) -> str:
    lines = [
        f"# Sill Garden Content Agent — {date.today().isoformat()}",
        "",
        f"Generated: {now_utc()}",
        "",
        "## Research",
        f"- Guides: {research_pack.get('guide_count')}",
        f"- Zero-click GSC queries: {len(research_pack.get('zero_click_queries') or [])}",
        f"- Network probes ok: {sum(1 for p in (research_pack.get('network_probes') or []) if p.get('ok'))}/"
        f"{len(research_pack.get('network_probes') or [])}",
        f"- LLM notes: {len(research_pack.get('llm_notes') or {})}",
        "",
        "## Applied",
    ]
    done = [a for a in applied if a.get("status") in ("applied", "dry-run")]
    if not done:
        lines.append("- No content changes this run.")
    for a in done:
        lines.append(
            f"- [{a.get('bucket', '?')}] {a.get('type')} -> `{a.get('slug')}` — {str(a.get('reason', ''))[:90]}"
        )
    lines.append("")
    lines.append("## Top demand")
    for q in (research_pack.get("zero_click_queries") or [])[:8]:
        lines.append(f"- {q.get('query')} — {q.get('impressions')} impr, pos {q.get('position')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sill Garden content agent")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.refresh and not args.dry_run:
        refresh_analytics()

    if not LATEST.is_file():
        print("Missing products/analytics/latest.json", file=sys.stderr)
        return 1

    metrics = metrics_from_latest()
    # Normalize query field names
    for q in metrics.get("top_queries") or []:
        if "ctr_pct" not in q and "ctr" in q:
            try:
                q["ctr_pct"] = float(q.get("ctr") or 0) * (100 if float(q.get("ctr") or 0) <= 1 else 1)
            except (TypeError, ValueError):
                q["ctr_pct"] = 0

    research_pack = research(metrics)
    actions = propose_actions(metrics, research_pack)
    applied = apply_actions(actions, dry_run=args.dry_run)

    indexnow = None
    if not args.dry_run and any(a.get("status") == "applied" for a in applied):
        indexnow = ping_indexnow()

    summary = summarize(research_pack, applied)
    report = {
        "date": date.today().isoformat(),
        "generated": now_utc(),
        "research": research_pack,
        "proposed": actions,
        "applied": applied,
        "indexnow": indexnow,
        "summary_md": summary,
    }
    save_json(OUT_DIR / f"{report['date']}.json", report)
    save_json(OUT_DIR / "latest.json", report)
    (OUT_DIR / f"{report['date']}.md").write_text(summary, encoding="utf-8")
    (OUT_DIR / "latest.md").write_text(summary, encoding="utf-8")
    save_json(
        STATE_PATH,
        {
            "last_run_at": now_utc(),
            "applied_count": sum(1 for a in applied if a.get("status") == "applied"),
            "dry_run": args.dry_run,
        },
    )
    try:
        print(summary)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(summary.encode("utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
