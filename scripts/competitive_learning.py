#!/usr/bin/env python3
"""Competitive / peer-site learning for growth iterations.

Each run:
1. Fetches configured peer pages (similar niche sites)
2. Extracts content + visuality signals from HTML
3. Optionally asks Perplexity/OpenAI what winners do differently
4. Writes products/growth/competitive-learning/latest.json
5. Returns actionable learnings for growth/content agents

  python scripts/competitive_learning.py
  python scripts/competitive_learning.py --max-peers 4
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_dotenv, load_json, save_json

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "products" / "growth" / "competitive-learning"
PEERS_PATH = ROOT / "products" / "growth" / "competitive-peers.json"
LATEST_ANALYTICS = ROOT / "products" / "analytics" / "latest.json"

USER_AGENT = "SillCompetitiveLearning/1.0 (+https://sillgarden.com)"


DEFAULT_PEERS = [
    {
        "name": "AeroGarden",
        "url": "https://www.aerogarden.com/",
        "kind": "brand",
        "why": "Category leader for countertop gardens",
    },
    {
        "name": "Click & Grow",
        "url": "https://www.clickandgrow.com/",
        "kind": "brand",
        "why": "Quiet kit competitor — silence/studio positioning",
    },
    {
        "name": "The Sill",
        "url": "https://www.thesill.com/",
        "kind": "editorial",
        "why": "Apartment plant brand — visual merchandising + guides",
    },
    {
        "name": "Gardener's Supply",
        "url": "https://www.gardeners.com/",
        "kind": "retail",
        "why": "Affiliate/retail peer — product card + CTA patterns",
    },
    {
        "name": "Gardening Know How (indoor)",
        "url": "https://www.gardeningknowhow.com/houseplants/",
        "kind": "editorial",
        "why": "SEO content depth for houseplant/indoor queries",
    },
    {
        "name": "Apartment Therapy plants",
        "url": "https://www.apartmenttherapy.com/tags/plants",
        "kind": "editorial",
        "why": "Lifestyle visual storytelling for apartments",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _strip_tags(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _meta(html: str, name: str) -> str | None:
    patterns = [
        rf'(?is)<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'(?is)<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return unescape(m.group(1)).strip()
    return None


def _first(html: str, pattern: str) -> str | None:
    m = re.search(pattern, html, re.I | re.S)
    return unescape(m.group(1)).strip() if m else None


def fetch_html(url: str, timeout: int = 18) -> dict[str, Any]:
    out: dict[str, Any] = {"url": url, "ok": False}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(180_000)
            html = raw.decode("utf-8", errors="replace")
            out["ok"] = True
            out["status"] = getattr(resp, "status", 200)
            out["bytes"] = len(raw)
            out["html"] = html
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:200]
    return out


def extract_signals(html: str, url: str) -> dict[str, Any]:
    title = _first(html, r"<title[^>]*>(.*?)</title>") or ""
    h1s = [unescape(x).strip() for x in re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", html)]
    h1s = [_strip_tags(f"<x>{h}</x>") for h in h1s if _strip_tags(f"<x>{h}</x>")]
    h2s = [unescape(x).strip() for x in re.findall(r"(?is)<h2[^>]*>(.*?)</h2>", html)]
    h2s = [_strip_tags(f"<x>{h}</x>") for h in h2s if _strip_tags(f"<x>{h}</x>")][:12]
    text = _strip_tags(html)
    words = len(text.split()) if text else 0
    faqish = bool(re.search(r"faq|frequently asked|questions\?", html, re.I))
    table = "<table" in html.lower()
    has_og_image = bool(_meta(html, "og:image"))
    has_json_ld = "application/ld+json" in html.lower()
    cta_hits = len(
        re.findall(
            r"(?i)(shop now|buy now|add to cart|get started|see pricing|compare|learn more|start free)",
            html,
        )
    )
    heroish = bool(
        re.search(r"(?i)(hero|banner|jumbotron|above.?the.?fold|full.?bleed)", html)
        or re.search(r"(?i)<header[^>]{0,200}class=[\"'][^\"']*(hero|banner)", html)
    )
    comparisonish = bool(re.search(r"(?i)(vs\.?|versus|compare|comparison)", title + " " + " ".join(h1s)))
    yearish = bool(re.search(r"\b202[5-7]\b", title + " " + " ".join(h1s[:1])))
    images = len(re.findall(r"(?i)<img\b", html))
    return {
        "url": url,
        "title": title[:140],
        "description": (_meta(html, "description") or _meta(html, "og:description") or "")[:220],
        "h1": h1s[:3],
        "h2_sample": h2s[:8],
        "word_count_est": words,
        "images": images,
        "has_faq": faqish,
        "has_table": table,
        "has_og_image": has_og_image,
        "has_json_ld": has_json_ld,
        "cta_mentions": cta_hits,
        "hero_signal": heroish,
        "comparison_signal": comparisonish,
        "year_in_title": yearish,
    }


def load_peers() -> list[dict]:
    configured = load_json(PEERS_PATH, None)
    if isinstance(configured, dict) and isinstance(configured.get("peers"), list):
        return [p for p in configured["peers"] if isinstance(p, dict) and p.get("url")]
    if isinstance(configured, list):
        return [p for p in configured if isinstance(p, dict) and p.get("url")]
    return list(DEFAULT_PEERS)


def _optional_llm_synthesis(peers: list[dict], our_queries: list[str]) -> str | None:
    load_dotenv()
    # Pull key from sibling projects if needed
    if not (os.environ.get("PERPLEXITY_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip():
        for path in (
            Path(r"E:/Projects/ai-visibility/.env"),
            Path(r"E:/Projects/makertoolstack/.env"),
        ):
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("PERPLEXITY_API_KEY=") or line.startswith("OPENAI_API_KEY="):
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    pplx = (os.environ.get("PERPLEXITY_API_KEY") or "").strip()
    oai = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not pplx and not oai:
        return None

    peer_lines = []
    for p in peers[:5]:
        sig = p.get("signals") or {}
        peer_lines.append(
            f"- {p.get('name')}: title={sig.get('title')!r}; h1={sig.get('h1')}; "
            f"faq={sig.get('has_faq')}; table={sig.get('has_table')}; "
            f"cta={sig.get('cta_mentions')}; hero={sig.get('hero_signal')}; words~{sig.get('word_count_est')}"
        )
    qline = ", ".join(our_queries[:5]) or "(none)"
    prompt = (
        "You advise an apartment indoor-garden affiliate site (Sill Garden). "
        "Given peer-site signals, list 5 concrete improvements for CONTENT and VISUALITY "
        "we can ship this week (titles, FAQ, comparison tables, hero/CTA layout, imagery). "
        "Be specific and actionable. No fluff.\n"
        f"Our GSC queries: {qline}\n"
        "Peers:\n" + "\n".join(peer_lines)
    )
    try:
        if pplx:
            from ai_growth_agent import perplexity_answer

            return (perplexity_answer(prompt, pplx) or "")[:1600]
        from ai_growth_agent import openai_answer

        return (openai_answer(prompt, oai) or "")[:1600]
    except Exception as exc:  # noqa: BLE001
        return f"(llm synthesis skipped: {exc})"[:200]


def _rule_learnings(peer_rows: list[dict], our: dict | None) -> list[str]:
    learnings: list[str] = []
    ok_rows = [r for r in peer_rows if (r.get("signals") or {}).get("title")]
    if not ok_rows:
        return ["Competitive crawl returned no usable peer pages — retry later."]

    faq_rate = sum(1 for r in ok_rows if (r.get("signals") or {}).get("has_faq")) / len(ok_rows)
    table_rate = sum(1 for r in ok_rows if (r.get("signals") or {}).get("has_table")) / len(ok_rows)
    year_rate = sum(1 for r in ok_rows if (r.get("signals") or {}).get("year_in_title")) / len(ok_rows)
    hero_rate = sum(1 for r in ok_rows if (r.get("signals") or {}).get("hero_signal")) / len(ok_rows)
    og_rate = sum(1 for r in ok_rows if (r.get("signals") or {}).get("has_og_image")) / len(ok_rows)
    avg_cta = sum(int((r.get("signals") or {}).get("cta_mentions") or 0) for r in ok_rows) / len(ok_rows)
    avg_words = sum(int((r.get("signals") or {}).get("word_count_est") or 0) for r in ok_rows) / len(ok_rows)

    if faq_rate >= 0.4:
        learnings.append(
            "WORKING peer pattern: FAQ blocks are common on similar sites — keep FAQ on money guides and match GSC question phrasing."
        )
    if table_rate >= 0.3:
        learnings.append(
            "WORKING peer pattern: comparison/spec tables appear often — keep side-by-side tables above the fold on vs guides."
        )
    if year_rate >= 0.3:
        learnings.append(
            "WORKING peer pattern: year-stamped titles (2026) — keep year in title/H1 on commercial guides for freshness CTR."
        )
    if hero_rate >= 0.4:
        learnings.append(
            "VISUAL peer pattern: hero/banner treatment is common — keep full-bleed hero + clear primary CTA; avoid cluttered first viewport."
        )
    if og_rate >= 0.5:
        learnings.append(
            "VISUAL peer pattern: og:image present on most peers — ensure every guide has a distinct social/hero image + alt."
        )
    if avg_cta >= 3:
        learnings.append(
            f"WORKING peer pattern: ~{avg_cta:.0f} CTA mentions/page — put verdict + product CTA early; repeat once mid-article."
        )
    if avg_words >= 800:
        learnings.append(
            f"WORKING peer pattern: long-form depth (~{avg_words:.0f} words avg) — expand thin guides with decision rules, not fluff."
        )

    # Gap vs our site probe
    if isinstance(our, dict) and our.get("ok"):
        our_sig = our.get("signals") or {}
        if faq_rate >= 0.4 and not our_sig.get("has_faq"):
            learnings.append("GAP: peers use FAQ more than our probed page — add FAQ matching top GSC queries.")
        if table_rate >= 0.3 and not our_sig.get("has_table"):
            learnings.append("GAP: peers use tables more — add a comparison table near the top of vs guides.")
        if our_sig.get("cta_mentions", 0) < max(2, avg_cta / 2):
            learnings.append("GAP: fewer CTAs than peers — raise above-fold verdict + product-card outbound links.")

    titles = [((r.get("signals") or {}).get("title") or "") for r in ok_rows]
    if any(" vs " in t.lower() or "versus" in t.lower() for t in titles):
        learnings.append(
            "DEMAND pattern: peers lean on 'X vs Y' titles — prioritize vs guides for GSC comparison queries."
        )
    return learnings[:10]


def propose_actions(learnings: list[str]) -> list[dict]:
    actions: list[dict] = []
    joined = " | ".join(learnings).lower()
    if "faq" in joined:
        actions.append(
            {
                "type": "content_faq",
                "priority": "P1",
                "title": "Add/refresh FAQ from peer + GSC questions",
                "detail": "Peers use FAQ heavily. Content agent should add 1–2 FAQs on money guides matching zero-click queries.",
                "auto": True,
            }
        )
    if "table" in joined or "comparison" in joined:
        actions.append(
            {
                "type": "content_table",
                "priority": "P1",
                "title": "Ensure comparison tables near top of vs guides",
                "detail": "Peers show side-by-side tables early. Keep Quick pick / side-by-side tables above long prose.",
                "auto": False,
            }
        )
    if "hero" in joined or "visual" in joined or "og:image" in joined:
        actions.append(
            {
                "type": "visuality",
                "priority": "P1",
                "title": "Visuality iteration: hero/CTA/og image hygiene",
                "detail": "Peers use hero imagery + clear CTA and og:image. Audit home + top guides for full-bleed hero, early verdict, unique images.",
                "auto": False,
            }
        )
    if "cta" in joined:
        actions.append(
            {
                "type": "cro_cta",
                "priority": "P1",
                "title": "Strengthen above-fold verdict + product CTAs",
                "detail": "Peers repeat CTAs. Keep Quick verdict + product picks before long narrative.",
                "auto": False,
            }
        )
    if "year" in joined or "2026" in joined:
        actions.append(
            {
                "type": "seo_year_stamp",
                "priority": "P2",
                "title": "Year-stamp commercial titles where missing",
                "detail": "Peers stamp year in titles. Growth/content agent should keep (2026) on money guides.",
                "auto": True,
            }
        )
    return actions


def run_competitive_learning(*, max_peers: int = 5, include_llm: bool = True) -> dict:
    peers_cfg = load_peers()[: max(1, max_peers)]
    peer_rows: list[dict] = []
    for peer in peers_cfg:
        url = str(peer.get("url") or "").strip()
        if not url:
            continue
        fetched = fetch_html(url)
        row = {
            "name": peer.get("name") or url,
            "kind": peer.get("kind") or "peer",
            "why": peer.get("why") or "",
            "url": url,
            "ok": fetched.get("ok"),
            "status": fetched.get("status"),
            "error": fetched.get("error"),
        }
        if fetched.get("ok") and fetched.get("html"):
            row["signals"] = extract_signals(fetched["html"], url)
        peer_rows.append(row)

    our = fetch_html("https://sillgarden.com/guides/aerogarden-vs-click-and-grow/")
    our_row: dict[str, Any] = {"url": our.get("url"), "ok": our.get("ok"), "error": our.get("error")}
    if our.get("ok") and our.get("html"):
        our_row["signals"] = extract_signals(our["html"], our["url"])

    analytics = load_json(LATEST_ANALYTICS, {}) or {}
    queries = [
        str(q.get("query") or "")
        for q in ((analytics.get("sources") or {}).get("gsc") or {}).get("top_queries") or []
        if q.get("query")
    ][:8]

    learnings = _rule_learnings(peer_rows, our_row)
    llm_notes = None
    if include_llm:
        llm_notes = _optional_llm_synthesis(peer_rows, queries)
        if llm_notes and not llm_notes.startswith("(llm"):
            for line in re.split(r"\n+", llm_notes):
                clean = re.sub(r"^[\d\.\-\*\)]\s*", "", line).strip()
                if len(clean) > 40:
                    learnings.append(f"LLM peer insight: {clean[:220]}")
            learnings = learnings[:12]

    actions = propose_actions(learnings)
    payload = {
        "generated_at": now_utc(),
        "site": "sillgarden",
        "peers": [{k: v for k, v in r.items() if k != "html"} for r in peer_rows],
        "our_probe": our_row,
        "gsc_queries": queries,
        "learnings": learnings,
        "llm_notes": llm_notes,
        "proposed_actions": actions,
        "ok_peers": sum(1 for r in peer_rows if r.get("ok")),
        "peer_count": len(peer_rows),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    day = now_utc()[:10]
    save_json(OUT_DIR / "latest.json", payload)
    save_json(OUT_DIR / f"{day}.json", payload)
    if not PEERS_PATH.is_file():
        save_json(PEERS_PATH, {"peers": DEFAULT_PEERS, "notes": "Edit to rotate peer set for learning."})
    return payload


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Competitive learning for Sill Garden")
    parser.add_argument("--max-peers", type=int, default=5)
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()
    payload = run_competitive_learning(max_peers=args.max_peers, include_llm=not args.skip_llm)
    print(f"Competitive learning OK · peers={payload['ok_peers']}/{payload['peer_count']}")
    for line in payload.get("learnings") or []:
        print(f"  - {line[:140]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
