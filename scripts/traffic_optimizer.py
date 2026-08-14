#!/usr/bin/env python3
"""Lightweight traffic actions from analytics (Sill Garden).

  python scripts/traffic_optimizer.py
  python scripts/traffic_optimizer.py --refresh
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "products" / "analytics" / "latest.json"
OUT_DIR = ROOT / "products" / "traffic"
QUEUE = OUT_DIR / "action-queue.json"
STATE = OUT_DIR / "optimizer-state.json"
MIN_HOURS_INDEXNOW = 20


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def task(priority: str, category: str, title: str, detail: str, *, auto: bool = False, done: bool = False) -> dict:
    return {
        "priority": priority,
        "category": category,
        "title": title,
        "detail": detail,
        "auto": auto,
        "done": done,
        "created": now_utc(),
    }


def hours_since(iso_or_display: str | None) -> float | None:
    if not iso_or_display:
        return None
    raw = iso_or_display.replace(" UTC", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except ValueError:
        return None


def build_queue(data: dict, state: dict) -> tuple[list[dict], dict, list[str]]:
    actions: list[dict] = []
    applied: list[str] = []
    hero = data.get("hero") or {}
    sources = data.get("sources") or {}
    gsc = sources.get("gsc") or {}
    ga4 = sources.get("ga4") or {}
    setup = data.get("setup") or {}

    sessions = hero.get("sessions_7d") or 0
    aff = hero.get("affiliate_clicks_7d") or 0
    gsc_clicks = hero.get("gsc_clicks_7d") or 0
    gsc_impr = hero.get("gsc_impressions_7d") or 0

    if sessions == 0:
        actions.append(
            task(
                "P0",
                "acquisition",
                "No GA4 sessions yet",
                "Share 1–2 guides or request indexing on home + top guides in Search Console.",
            )
        )
    if gsc_impr == 0 and not gsc.get("error"):
        actions.append(
            task(
                "P0",
                "indexing",
                "GSC impressions still 0",
                "Sitemap is submitted; wait for crawl or Request indexing on priority URLs.",
            )
        )

    # Near-page-1 opportunities
    for q in (gsc.get("top_queries") or [])[:15]:
        pos = q.get("position")
        clicks = q.get("clicks") or 0
        impr = q.get("impressions") or 0
        query = q.get("query") or ""
        if not query or pos is None:
            continue
        if 4 <= float(pos) <= 20 and impr >= 10 and clicks < max(2, impr * 0.05):
            actions.append(
                task(
                    "P1",
                    "seo",
                    f"Improve CTR / depth for “{query}”",
                    f"pos {pos:.1f}, {impr} impr, {clicks} clicks — tighten title/meta or add a sharper intro.",
                )
            )

    for page in (gsc.get("top_pages") or (ga4.get("top_pages") or []))[:8]:
        url = page.get("page") or page.get("path") or ""
        if "/guides/" in url and (page.get("clicks") or page.get("screenPageViews") or 0) > 0:
            actions.append(
                task(
                    "P2",
                    "content",
                    f"Refresh guide: {url.rstrip('/').split('/')[-1]}",
                    "Add a mid-article product pick or FAQ if affiliate clicks lag sessions.",
                )
            )

    ready = (setup.get("ready") or 0), (setup.get("total") or 7)
    if ready[0] < ready[1]:
        for c in setup.get("checks") or []:
            if not c.get("ok"):
                actions.append(
                    task("P2", "setup", f"Finish setup: {c.get('name')}", str(c.get("detail") or "")[:200])
                )

    if sessions > 0 and aff == 0:
        actions.append(
            task(
                "P1",
                "monetization",
                "Traffic without affiliate clicks",
                "Confirm Amazon CTAs fire affiliate_click and links use sillgarden09-20.",
            )
        )

    # Throttled IndexNow (auto)
    hrs = hours_since(state.get("lastIndexNowAt"))
    if hrs is None or hrs >= MIN_HOURS_INDEXNOW:
        try:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "submit_indexing.py")],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if proc.returncode == 0 and "IndexNow OK" in (proc.stdout + proc.stderr):
                state["lastIndexNowAt"] = now_utc()
                applied.append("IndexNow ping")
                actions.append(
                    task("P3", "indexing", "IndexNow ping", "Re-notified Bing/Yandex of sitemap URLs.", auto=True, done=True)
                )
            else:
                actions.append(
                    task(
                        "P3",
                        "indexing",
                        "IndexNow ping skipped/failed",
                        ((proc.stdout or "") + (proc.stderr or ""))[:240],
                        auto=True,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            actions.append(task("P3", "indexing", "IndexNow error", str(exc)[:200], auto=True))
    else:
        actions.append(
            task(
                "P3",
                "indexing",
                "IndexNow throttled",
                f"Last ping {state.get('lastIndexNowAt')} ({hrs:.1f}h ago; min {MIN_HOURS_INDEXNOW}h).",
                auto=True,
                done=True,
            )
        )

    # Deduplicate by title
    seen: set[str] = set()
    unique: list[dict] = []
    for a in actions:
        if a["title"] in seen:
            continue
        seen.add(a["title"])
        unique.append(a)

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    unique.sort(key=lambda a: priority_order.get(a["priority"], 9))
    state["runs"] = int(state.get("runs") or 0) + 1
    state["lastRunAt"] = now_utc()
    return unique[:25], state, applied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Run analytics_summary first")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "scripts"))
    from analytics_summary import load_dotenv
    from measurement_gate import require_google_access

    load_dotenv()

    if args.refresh:
        from analytics_summary import main as summary_main

        summary_main()

    gate = require_google_access(strict=False, warn_only=True)
    data = load_json(LATEST, {})
    if not data:
        print("No latest.json — run analytics_summary.py first", file=sys.stderr)
        return 1

    state = load_json(STATE, {"lastIndexNowAt": None, "runs": 0})
    queue, state, applied = build_queue(data, state)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": now_utc(),
        "site_url": "https://sillgarden.com",
        "gate_ok": gate == 0,
        "applied": applied,
        "actions": queue,
    }
    QUEUE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "actions": len(queue), "applied": applied}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
