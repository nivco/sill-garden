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
    featured = [g for g in guides if g.frontmatter.get("featured")]
    pool = featured or guides
    # Prefer guides matching top GSC queries.
    top = (metrics.get("top_queries") or [])[:5]
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


def build_distribution_pack(metrics: dict | None = None) -> dict:
    target = pick_distribution_target(metrics)
    if not target:
        return {"ok": False, "error": "no guides"}
    base = site_url()
    pack = {
        "generated_at": now_utc(),
        "target": target,
        "channels": {
            "x": f"{target['title']}\n\n{target['url']}\n\n#IndoorGarden #ApartmentLiving",
            "bluesky": f"{target['title']}\n\n{target['description']}\n\n{target['url']}",
            "mastodon": f"{target['title']}\n\n{target['url']}\n\n#IndoorGarden #ApartmentLiving #Herbs",
            "reddit": (
                f"Title idea: {target['title']}\n\n"
                f"Body: {target['description']}\n\n"
                f"Link: {target['url']}\n"
                f"Disclosure: {base}/disclosure/"
            ),
            "devto": f"Syndicate canonical: {target['url']}",
        },
    }
    return pack


def save_distribution_pack(pack: dict) -> Path:
    day = now_utc()[:10]
    path = DIST_DIR / f"{day}.json"
    save_json(path, pack)
    save_json(DIST_DIR / "latest.json", pack)
    return path


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
