#!/usr/bin/env python3
"""Build unified Sill Garden growth summary emails (MTS-style ops report)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "products" / "analytics" / "latest.json"
LEARNING = ROOT / "products" / "analytics" / "learning-snapshot.json"
TRAFFIC_QUEUE = ROOT / "products" / "traffic" / "action-queue.json"
BOARD_QUEUE = ROOT / "reports" / "board" / "action-queue.json"
DIST = ROOT / "products" / "growth" / "distribution" / "latest.json"
OUTCOME = ROOT / "products" / "growth" / "outcome-health.json"
YT_STATE = ROOT / "products" / "youtube" / "publish-state.json"
HISTORY = ROOT / "products" / "analytics" / "history.json"


def _load(path: Path) -> dict | list:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _ascii_safe(text: str) -> str:
    return (
        text.replace("\u2248", "~")
        .replace("\u2192", "->")
        .replace("\u2014", "-")
        .replace("\u00b7", " | ")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _disp(value, default: str = "-") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _sessions_from_history(days_ago: int = 5) -> int | None:
    history = _load(HISTORY)
    if not isinstance(history, list) or not history:
        return None
    target = date.fromordinal(date.today().toordinal() - days_ago).isoformat()
    best = None
    best_day = ""
    for entry in history:
        if not isinstance(entry, dict):
            continue
        day = str(entry.get("generated_at") or "")[:10]
        if not day or day > target:
            continue
        sess = entry.get("ga4_sessions_7d")
        if sess is None and isinstance(entry.get("hero"), dict):
            sess = entry["hero"].get("sessions_7d")
        if sess is None:
            continue
        if day >= best_day:
            best_day = day
            best = int(sess or 0)
    return best


def build_unified_growth_email(
    *,
    header_title: str = "Sill Garden Traffic & Growth Summary",
    cadence: str | None = None,
    applied: list | None = None,
    learnings: list[str] | None = None,
    outcome: dict | None = None,
    distribution: dict | None = None,
) -> dict:
    today = date.today().isoformat()
    latest = _load(LATEST) if isinstance(_load(LATEST), dict) else {}
    hero = (latest.get("hero") or {}) if isinstance(latest, dict) else {}
    sources = (latest.get("sources") or {}) if isinstance(latest, dict) else {}
    gsc = sources.get("gsc") or {}
    yt = (sources.get("youtube") or {}).get("channel") or {}
    learning = _load(LEARNING) if isinstance(_load(LEARNING), dict) else {}
    traffic = _load(TRAFFIC_QUEUE) if isinstance(_load(TRAFFIC_QUEUE), dict) else {}
    board = _load(BOARD_QUEUE) if isinstance(_load(BOARD_QUEUE), dict) else {}
    dist = distribution or (_load(DIST) if isinstance(_load(DIST), dict) else {})
    health = outcome or (_load(OUTCOME) if isinstance(_load(OUTCOME), dict) else {})
    yt_state = _load(YT_STATE) if isinstance(_load(YT_STATE), dict) else {}

    sessions = hero.get("sessions_7d")
    baseline = _sessions_from_history(5)
    delta = ""
    if sessions is not None and baseline is not None:
        change = int(sessions) - int(baseline)
        sign = "+" if change > 0 else ""
        delta = f" ({sign}{change} vs 5d ago)"

    open_traffic = [a for a in (traffic.get("actions") or []) if not a.get("done")]
    open_board = [
        i
        for i in (board.get("items") or [])
        if not i.get("done") and (i.get("role") or "") != "ai-visibility"
    ]
    learnings = learnings or (learning.get("learnings") or [])[:6]
    applied = applied or []

    lines = [
        f"# {_ascii_safe(header_title)}",
        f"**{today}**"
        + (f" · {cadence.upper()}" if cadence else "")
        + f" · severity {(health.get('severity') or 'ok')}",
        "",
        "## At a glance",
        f"- **Sessions (7d):** **{_disp(sessions)}**{delta}",
        f"- **GSC:** {_disp(hero.get('gsc_impressions_7d'))} impr / {_disp(hero.get('gsc_clicks_7d'))} clicks",
        f"- **Affiliate clicks:** {_disp(hero.get('affiliate_clicks_7d'))}",
        f"- **YouTube:** {_disp(yt.get('views') or hero.get('youtube_views_total'))} views · "
        f"{_disp(yt.get('subscribers') or hero.get('youtube_subs'))} subs · "
        f"YT->site {_disp(hero.get('youtube_sessions_7d'))}",
        f"- **Next YT eligible:** {_disp(yt_state.get('next_eligible_date'))}",
        "",
        "## Outcome health",
    ]
    if health.get("reasons"):
        lines.extend(f"- {r}" for r in health["reasons"])
    else:
        lines.append("- OK")
    if health.get("actions"):
        lines.append("- Do next:")
        lines.extend(f"  - {a}" for a in health["actions"][:4])

    lines.extend(["", "## Do next (traffic queue)"])
    if open_traffic:
        for a in open_traffic[:6]:
            lines.append(
                f"- [{a.get('priority') or 'P2'}] {a.get('title')}: {(a.get('detail') or '')[:140]}"
            )
    else:
        lines.append("- No open traffic actions")

    lines.extend(["", "## Board open"])
    if open_board:
        for item in open_board[:6]:
            lines.append(f"- [{item.get('priority')}] [{item.get('role')}] {item.get('title')}")
    else:
        lines.append("- No open board items")

    lines.extend(["", "## Applied / learning"])
    if applied:
        for item in applied[:8]:
            if isinstance(item, dict):
                lines.append(f"- {item.get('type') or item.get('title') or item}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("- None this run")
    for item in learnings[:5]:
        lines.append(f"- LEARN: {item}")

    comp = _load(ROOT / "products" / "growth" / "competitive-learning" / "latest.json")
    if isinstance(comp, dict) and (comp.get("learnings") or comp.get("ok_peers") is not None):
        lines.extend(["", "## Competitive learning (peer sites)"])
        lines.append(f"- Peers ok: {_disp(comp.get('ok_peers'))}/{_disp(comp.get('peer_count'))}")
        for item in (comp.get("learnings") or [])[:5]:
            lines.append(f"- {item}")

    target = (dist.get("target") or {}) if isinstance(dist, dict) else {}
    channels = (dist.get("channels") or {}) if isinstance(dist, dict) else {}
    lines.extend(["", "## Distribution pack"])
    if target.get("url"):
        lines.append(f"- Target: {target.get('title')} — {target.get('url')}")
        lines.append(f"- Reason: {target.get('reason') or '-'}")
        if channels.get("reddit"):
            lines.append("- Reddit draft:")
            lines.append(channels["reddit"][:500])
        if channels.get("bluesky"):
            lines.append(f"- Bluesky: {channels['bluesky'][:220]}")
    else:
        lines.append("- No distribution pack yet")

    lines.extend(
        [
            "",
            "---",
            "[Dashboard](http://127.0.0.1:8793/dashboard) · [Site](https://sillgarden.com)",
            f"generated {(latest.get('generated_at') if isinstance(latest, dict) else '-')}",
        ]
    )

    body = _ascii_safe("\n".join(lines))
    severity = (health.get("severity") or "ok").upper()
    subject = f"Sill Garden · {severity} · sessions {_disp(sessions)} · {today}"
    return {
        "date": today,
        "email_subject": subject,
        "email_body": body,
        "summary_text": body,
        "metrics": {
            "sessions_7d": sessions,
            "gsc_impressions_7d": hero.get("gsc_impressions_7d"),
            "gsc_clicks_7d": hero.get("gsc_clicks_7d"),
            "affiliate_clicks_7d": hero.get("affiliate_clicks_7d"),
            "youtube_views_total": yt.get("views") or hero.get("youtube_views_total"),
            "youtube_sessions_7d": hero.get("youtube_sessions_7d"),
        },
        "outcome_severity": health.get("severity"),
    }
