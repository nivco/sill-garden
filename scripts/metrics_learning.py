#!/usr/bin/env python3
"""Build a durable learning snapshot from Sill Garden analytics history."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_json, now_utc, save_json

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "products" / "analytics" / "latest.json"
HISTORY = ROOT / "products" / "analytics" / "history.json"
YT_CONTENT = ROOT / "products" / "youtube" / "content-history.json"
OUT = ROOT / "products" / "analytics" / "learning-snapshot.json"
PLAYBOOK = ROOT / "products" / "analytics" / "working-playbook.json"


def build_learning() -> dict:
    latest = load_json(LATEST, {}) or {}
    history = load_json(HISTORY, []) or []
    if isinstance(history, dict):
        history = history.get("snapshots") or history.get("history") or []
    sources = latest.get("sources") or {}
    gsc = sources.get("gsc") or {}
    ga4 = sources.get("ga4") or {}
    yt = sources.get("youtube") or {}
    hero = latest.get("hero") or {}

    snaps = sorted(history, key=lambda r: r.get("generated_at") or r.get("date") or "")
    wow: dict[str, float] = {}
    if len(snaps) >= 2:
        a, b = snaps[0], snaps[-1]
        if len(snaps) >= 8:
            a = snaps[-8]
        for key in ("ga4_sessions_7d", "gsc_impressions_7d", "gsc_clicks_7d", "affiliate_clicks_7d"):
            try:
                wow[key] = float(b.get(key) or 0) - float(a.get(key) or 0)
            except (TypeError, ValueError):
                pass

    learnings: list[str] = []
    playbook = load_json(PLAYBOOK, {}) or {}
    for item in playbook.get("working") or []:
        status = item.get("status") or "working"
        prefix = "WORKING" if status == "working" else "IGNORE"
        learnings.append(f"{prefix}: {item.get('signal')} → {item.get('action')}")

    impr = float(gsc.get("impressions") or hero.get("gsc_impressions_7d") or 0)
    clicks = float(gsc.get("clicks") or hero.get("gsc_clicks_7d") or 0)
    if impr > 0 and clicks == 0:
        learnings.append(
            "GSC has impressions with 0 clicks — tighten titles/meta on early-ranking guides before more thin pages."
        )
    top_q = gsc.get("top_queries") or []
    if top_q:
        lead = top_q[0]
        learnings.append(
            f"Top search demand: \"{lead.get('query')}\" "
            f"({lead.get('impressions')} impr, pos {lead.get('position')})."
        )
    sessions = float((ga4.get("totals") or {}).get("sessions") or hero.get("sessions_7d") or 0)
    aff = float(hero.get("affiliate_clicks_7d") or 0)
    if sessions >= 20 and aff == 0:
        learnings.append("Sessions without affiliate clicks — check product CTAs and GA4 affiliate_click events.")
    elif sessions and aff:
        learnings.append(f"Affiliate CTR signal: {aff:.0f} clicks / {sessions:.0f} sessions.")

    yt_ch = yt.get("channel") or {}
    if yt_ch.get("videos"):
        learnings.append(
            f"YouTube channel: {yt_ch.get('videos')} videos, {yt_ch.get('views')} views, "
            f"{hero.get('youtube_sessions_7d') or 0} site sessions from YouTube."
        )
    content = load_json(YT_CONTENT, {}) or {}
    published = content.get("published") or content.get("items") or []
    if published:
        learnings.append(f"YouTube publish log entries: {len(published)}.")

    if not learnings:
        learnings.append("Not enough history yet — keep daily analytics + IndexNow running.")

    snapshot = {
        "generated_at": now_utc(),
        "wow": wow,
        "hero": {
            "sessions_7d": hero.get("sessions_7d"),
            "gsc_impressions_7d": hero.get("gsc_impressions_7d"),
            "gsc_clicks_7d": hero.get("gsc_clicks_7d"),
            "affiliate_clicks_7d": hero.get("affiliate_clicks_7d"),
            "youtube_sessions_7d": hero.get("youtube_sessions_7d"),
            "indexed_urls": hero.get("indexed_urls"),
        },
        "top_queries": top_q[:10],
        "learnings": learnings,
    }
    save_json(OUT, snapshot)
    return snapshot


def main() -> int:
    snap = build_learning()
    print(f"Wrote {OUT} ({len(snap.get('learnings') or [])} learnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
