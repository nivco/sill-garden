#!/usr/bin/env python3
"""Weekly AI citation check for Sill Garden (Perplexity/OpenAI when keys exist).

  python scripts/ai_growth_agent.py --demo
  python scripts/ai_growth_agent.py --dry-run
  python scripts/ai_growth_agent.py --enqueue
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_dotenv, load_json, now_utc, save_json
from board_actions import enqueue

ROOT = Path(__file__).resolve().parents[1]
PROMPTS_PATH = ROOT / "data" / "ai-growth-prompts.json"
OUT_DIR = ROOT / "products" / "growth" / "ai-citation"
LATEST_PATH = OUT_DIR / "latest.json"

BRAND = "Sill Garden"
DOMAIN = "sillgarden.com"
ALIASES = ["Sill Garden", "sillgarden", "sillgarden.com"]


def detect_mention(text: str) -> dict[str, bool]:
    lower = (text or "").lower()
    name_hit = any(a.lower() in lower for a in ALIASES)
    domain_hit = DOMAIN in lower
    url_hit = bool(re.search(rf"https?://(?:www\.)?{re.escape(DOMAIN)}", lower))
    return {"name": name_hit, "domain": domain_hit or url_hit, "any": name_hit or domain_hit or url_hit}


def demo_answer(prompt: str) -> str:
    # Offline deterministic answers — used in CI without API keys.
    if "aerogarden" in prompt.lower() and "click" in prompt.lower():
        return (
            "Popular options include AeroGarden and Click & Grow. "
            "Independent apartment-focused comparisons also appear on gardening blogs."
        )
    if "low light" in prompt.lower() or "windowsill" in prompt.lower():
        return "Mint, chives, parsley, and oregano are commonly recommended for dim apartment windowsills."
    return "I don't have a specific brand recommendation for that apartment gardening question."


def openai_answer(prompt: str, api_key: str) -> str:
    payload = {
        "model": os.environ.get("OPENAI_MODEL") or "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "Answer briefly with concrete product or site recommendations when relevant.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SillGarden/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""


def perplexity_answer(prompt: str, api_key: str) -> str:
    payload = {
        "model": os.environ.get("PERPLEXITY_MODEL") or "sonar",
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.perplexity.ai/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SillGarden/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""


def default_prompts() -> list[dict[str, str]]:
    return [
        {"id": "ag-vs-cg", "prompt": "AeroGarden vs Click and Grow for a small apartment kitchen — which should I buy?"},
        {"id": "low-light", "prompt": "Best low light herbs for an apartment windowsill?"},
        {"id": "quiet", "prompt": "Quietest countertop garden for a studio apartment?"},
        {"id": "landlord", "prompt": "Landlord-safe indoor garden setup that won't risk my deposit?"},
        {"id": "cheap", "prompt": "Cheapest way to grow herbs indoors in an apartment under $50?"},
    ]


def load_prompts() -> list[dict[str, str]]:
    data = load_json(PROMPTS_PATH, None)
    if isinstance(data, dict) and isinstance(data.get("prompts"), list):
        return data["prompts"]
    if isinstance(data, list):
        return data
    return default_prompts()


def run_probe(*, demo: bool) -> dict[str, Any]:
    prompts = load_prompts()
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    pplx_key = (os.environ.get("PERPLEXITY_API_KEY") or "").strip()
    rows = []
    mentions = 0
    for item in prompts:
        prompt = item.get("prompt") or ""
        answer = ""
        provider = "demo"
        try:
            if demo or (not openai_key and not pplx_key):
                answer = demo_answer(prompt)
                provider = "demo"
            elif pplx_key:
                answer = perplexity_answer(prompt, pplx_key)
                provider = "perplexity"
            else:
                answer = openai_answer(prompt, openai_key)
                provider = "openai"
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            answer = f"[error] {exc}"
            provider = f"{provider}-error"
        hit = detect_mention(answer)
        if hit["any"]:
            mentions += 1
        rows.append(
            {
                "id": item.get("id"),
                "prompt": prompt,
                "provider": provider,
                "answer": answer[:1200],
                "mention": hit,
            }
        )
    total = len(rows) or 1
    report = {
        "generated_at": now_utc(),
        "brand": BRAND,
        "domain": DOMAIN,
        "visibility_score": round(mentions / total, 3),
        "mentions": mentions,
        "prompts": total,
        "rows": rows,
    }
    return report


def enqueue_misses(report: dict, *, demo: bool = False) -> list[str]:
    if demo:
        # Demo answers never cite the brand — don't flood the board.
        return []
    created = []
    for row in report.get("rows") or []:
        if (row.get("mention") or {}).get("any"):
            continue
        item = enqueue(
            role="ai-visibility",
            action_type="earn_citation",
            title=f"Earn AI citation: {row.get('id')}",
            detail=f"Prompt not citing {BRAND}: {row.get('prompt')}",
            target=str(row.get("id") or ""),
            auto=False,
            priority="P3",
        )
        if item:
            created.append(item["title"])
    return created


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--enqueue", action="store_true")
    args = parser.parse_args()

    report = run_probe(demo=args.demo)
    if not args.dry_run:
        save_json(LATEST_PATH, report)
        day = date.today().isoformat()
        save_json(OUT_DIR / "history" / f"{day}.json", report)
    print(
        f"AI growth: visibility={report['visibility_score']} "
        f"mentions={report['mentions']}/{report['prompts']} demo={args.demo}"
    )
    if args.enqueue and not args.dry_run:
        created = enqueue_misses(report, demo=args.demo)
        print(f"Enqueued {len(created)} citation tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
