#!/usr/bin/env python3
"""Record growth actions with baselines and score their impact later.

Used by daily_growth_agent:
  1) score prior actions (3d / 7d windows)
  2) record today's applied actions against current hero metrics
  3) fold outcomes into working-playbook + learning-snapshot lines

Session retros in products/growth/session-retros/ teach *how* we decide.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_json, now_utc, save_json

ROOT = Path(__file__).resolve().parents[1]
GROWTH = ROOT / "products" / "growth"
LOG_PATH = GROWTH / "action-impact-log.json"
PLAYBOOK = ROOT / "products" / "analytics" / "working-playbook.json"
RETROS = GROWTH / "session-retros"
LATEST = ROOT / "products" / "analytics" / "latest.json"
HISTORY = ROOT / "products" / "analytics" / "history.json"

METRIC_KEYS = (
    "sessions_7d",
    "gsc_impressions_7d",
    "gsc_clicks_7d",
    "affiliate_clicks_7d",
    "youtube_sessions_7d",
    "youtube_views_total",
)

# Days after execute before we score.
WINDOW_DAYS = 3
FINAL_DAYS = 7


def _parse_day(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip().replace(" UTC", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def hero_metrics(latest: dict | None = None) -> dict[str, float | int | None]:
    latest = latest or load_json(LATEST, {}) or {}
    hero = latest.get("hero") or {}
    out: dict[str, float | int | None] = {}
    for key in METRIC_KEYS:
        val = hero.get(key)
        if val is None and key.startswith("gsc_"):
            gsc = (latest.get("sources") or {}).get("gsc") or {}
            alt = key.replace("gsc_", "").replace("_7d", "")
            val = gsc.get(alt) if alt in gsc else hero.get(key)
        try:
            out[key] = None if val is None else float(val)
        except (TypeError, ValueError):
            out[key] = None
    return out


def load_log() -> dict:
    data = load_json(LOG_PATH, None)
    if isinstance(data, dict):
        data.setdefault("version", 1)
        data.setdefault("actions", [])
        data.setdefault("session_retros_ingested", [])
        return data
    return {"version": 1, "actions": [], "session_retros_ingested": []}


def save_log(log: dict) -> None:
    log["updated_at"] = now_utc()
    save_json(LOG_PATH, log)


def _action_id(kind: str, target: str, day: str) -> str:
    raw = f"{kind}|{target}|{day}".lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:14]


def session_lesson_lines(limit: int = 12) -> list[str]:
    """Turn session retros into durable learning lines for the agent."""
    lines: list[str] = []
    if not RETROS.is_dir():
        return lines
    for path in sorted(RETROS.glob("*.json"), reverse=True):
        data = load_json(path, {}) or {}
        title = data.get("title") or path.stem
        lines.append(f"SESSION ({data.get('date') or path.stem}): {title}")
        for rule in (data.get("rules_to_keep") or [])[:6]:
            lines.append(f"SESSION-RULE: {rule}")
        for step in (data.get("decision_framework") or [])[:4]:
            lines.append(f"SESSION-FRAME: {step}")
        for item in (data.get("questions_asked") or [])[:4]:
            q = (item.get("q") or "")[:90]
            d = (item.get("decision") or "")[:140]
            if q and d:
                lines.append(f"SESSION-Q: {q} -> {d}")
        if len(lines) >= limit:
            break
    return lines[:limit]


def ingest_session_retros(log: dict | None = None) -> list[dict]:
    """Ensure each session retro is logged as a measuring 'cycle' action once."""
    log = log or load_log()
    seen = set(log.get("session_retros_ingested") or [])
    created: list[dict] = []
    if not RETROS.is_dir():
        return created
    for path in sorted(RETROS.glob("*.json")):
        rid = path.stem
        if rid in seen:
            continue
        data = load_json(path, {}) or {}
        baseline = data.get("baseline_metrics_at_close") or hero_metrics()
        # Drop non-metric notes
        metrics = {k: baseline.get(k) for k in METRIC_KEYS if k in baseline}
        if not any(v is not None for v in metrics.values()):
            metrics = hero_metrics()
        day = str(data.get("date") or now_utc()[:10])
        action = {
            "id": _action_id("session_cycle", rid, day),
            "kind": "session_cycle",
            "target": rid,
            "title": data.get("title") or rid,
            "detail": "; ".join((data.get("rules_to_keep") or [])[:3]),
            "source": "session_retro",
            "status": "measuring",
            "executed_at": day,
            "measure_after": (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=WINDOW_DAYS))
            .date()
            .isoformat(),
            "final_after": (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=FINAL_DAYS))
            .date()
            .isoformat(),
            "metrics_before": metrics,
            "primary_metric": "sessions_7d",
            "success_criteria": data.get("success_criteria_3_7d") or [],
        }
        log["actions"].append(action)
        seen.add(rid)
        created.append(action)
        # Also track each shipped money surface from the retro for page-level impact.
        for url in data.get("shipped_surfaces") or []:
            slug = str(url).rstrip("/").split("/")[-1] or "home"
            page_action = {
                "id": _action_id("ship_surface", slug, day),
                "kind": "ship_surface",
                "target": slug,
                "title": f"Shipped {url}",
                "detail": f"From session retro {rid}",
                "source": "session_retro",
                "status": "measuring",
                "executed_at": day,
                "measure_after": action["measure_after"],
                "final_after": action["final_after"],
                "metrics_before": metrics,
                "primary_metric": "sessions_7d" if "/kits" in url or "/tools" in url else "gsc_impressions_7d",
            }
            # Prefer affiliate signal for money URLs once traffic exists.
            if any(x in url for x in ("/kits", "/tools")):
                page_action["primary_metric"] = "affiliate_clicks_7d"
            log["actions"].append(page_action)
            created.append(page_action)
    log["session_retros_ingested"] = sorted(seen)
    save_log(log)
    return created


def backfill_shipped_surfaces() -> list[dict]:
    """Add ship_surface rows for retros already ingested before surface tracking existed."""
    log = load_log()
    existing = {(a.get("kind"), a.get("target"), a.get("executed_at")) for a in log.get("actions") or []}
    created: list[dict] = []
    if not RETROS.is_dir():
        return created
    for path in sorted(RETROS.glob("*.json")):
        data = load_json(path, {}) or {}
        day = str(data.get("date") or now_utc()[:10])
        baseline = data.get("baseline_metrics_at_close") or hero_metrics()
        metrics = {k: baseline.get(k) for k in METRIC_KEYS if k in baseline}
        if not any(v is not None for v in metrics.values()):
            metrics = hero_metrics()
        measure_after = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=WINDOW_DAYS)).date().isoformat()
        final_after = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=FINAL_DAYS)).date().isoformat()
        for url in data.get("shipped_surfaces") or []:
            slug = str(url).rstrip("/").split("/")[-1] or "home"
            key = ("ship_surface", slug, day)
            if key in existing:
                continue
            page_action = {
                "id": _action_id("ship_surface", slug, day),
                "kind": "ship_surface",
                "target": slug,
                "title": f"Shipped {url}",
                "detail": f"From session retro {path.stem}",
                "source": "session_retro",
                "status": "measuring",
                "executed_at": day,
                "measure_after": measure_after,
                "final_after": final_after,
                "metrics_before": metrics,
                "primary_metric": "affiliate_clicks_7d"
                if any(x in url for x in ("/kits", "/tools"))
                else "gsc_impressions_7d",
            }
            log["actions"].append(page_action)
            existing.add(key)
            created.append(page_action)
    if created:
        save_log(log)
    return created


def record_actions(
    applied: list[str] | list[dict],
    *,
    metrics: dict | None = None,
    source: str = "daily_growth_agent",
) -> list[dict]:
    """Snapshot today's applied work for later impact scoring."""
    log = load_log()
    snap = metrics or hero_metrics()
    today = now_utc()[:10]
    measure_after = (datetime.now(timezone.utc) + timedelta(days=WINDOW_DAYS)).date().isoformat()
    final_after = (datetime.now(timezone.utc) + timedelta(days=FINAL_DAYS)).date().isoformat()
    recorded: list[dict] = []
    existing = {(a.get("kind"), a.get("target"), a.get("executed_at")) for a in log.get("actions") or []}

    for raw in applied:
        if isinstance(raw, dict):
            kind = str(raw.get("type") or raw.get("kind") or "action")
            target = str(raw.get("slug") or raw.get("target") or raw.get("title") or kind)
            title = str(raw.get("title") or raw.get("reason") or target)
            detail = str(raw.get("detail") or raw.get("reason") or "")
            primary = str(raw.get("primary_metric") or "sessions_7d")
        else:
            text = str(raw).strip()
            if not text or text.startswith("[dry-run]") or "failed:" in text:
                continue
            kind = "applied"
            target = text.split("—")[0].split(":")[-1].strip()[:80] or text[:80]
            title = text[:160]
            detail = text
            primary = "sessions_7d"
            if "indexnow" in text.lower() or "indexing" in text.lower():
                primary = "gsc_impressions_7d"
            elif "youtube" in text.lower() or "kit comment" in text.lower():
                primary = "youtube_sessions_7d"
            elif "affiliate" in text.lower() or "kit" in text.lower():
                primary = "affiliate_clicks_7d"
            elif "tune_guide_seo" in text.lower() or "seo" in text.lower():
                primary = "gsc_clicks_7d"

        key = (kind, target, today)
        if key in existing:
            continue
        action = {
            "id": _action_id(kind, target, today),
            "kind": kind,
            "target": target,
            "title": title,
            "detail": detail[:300],
            "source": source,
            "status": "measuring",
            "executed_at": today,
            "measure_after": measure_after,
            "final_after": final_after,
            "metrics_before": snap,
            "primary_metric": primary,
        }
        log["actions"].append(action)
        existing.add(key)
        recorded.append(action)

    if recorded:
        save_log(log)
    return recorded


def _delta(before: dict, after: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for key in METRIC_KEYS:
        b, a = before.get(key), after.get(key)
        if b is None or a is None:
            continue
        try:
            out[key] = float(a) - float(b)
        except (TypeError, ValueError):
            continue
    return out


def _verdict(delta: dict[str, float], primary: str) -> tuple[str, str]:
    d = delta.get(primary)
    if d is None:
        # Fall back: any positive traffic/money signal
        for key in ("sessions_7d", "gsc_clicks_7d", "affiliate_clicks_7d", "youtube_sessions_7d"):
            if delta.get(key, 0) > 0:
                return "positive", f"lift on {key} {delta[key]:+.0f} (primary {primary} unavailable)"
        return "inconclusive", "no comparable primary metric"
    if d > 0:
        return "positive", f"positive {primary} {d:+.0f}"
    if d < 0:
        return "negative", f"negative {primary} {d:+.0f}"
    return "flat", f"flat {primary} (0)"


def measure_due_actions(*, metrics: dict | None = None, today: str | None = None) -> list[dict]:
    """Close measuring actions whose window elapsed; update playbook on repeats."""
    log = load_log()
    ingest_session_retros(log)
    backfill_shipped_surfaces()
    log = load_log()
    snap = metrics or hero_metrics()
    today = today or datetime.now(timezone.utc).date().isoformat()
    closed: list[dict] = []

    for action in log.get("actions") or []:
        if action.get("status") != "measuring":
            continue
        measure_after = action.get("measure_after") or ""
        if measure_after > today:
            continue
        before = action.get("metrics_before") or {}
        delta = _delta(before, snap)
        primary = action.get("primary_metric") or "sessions_7d"
        verdict, outcome = _verdict(delta, primary)
        action["metrics_after"] = snap
        action["delta"] = delta
        action["verdict"] = verdict
        action["outcome"] = outcome
        action["measured_at"] = now_utc()
        # Keep measuring until final window for a second look, else complete.
        final_after = action.get("final_after") or measure_after
        if final_after > today and verdict == "flat":
            action["status"] = "measuring"
            action["measure_after"] = final_after
            action["interim_outcome"] = outcome
        else:
            action["status"] = "completed"
        closed.append(dict(action))

    if closed:
        save_log(log)
        _apply_verdicts_to_playbook(closed)
    return closed


def _apply_verdicts_to_playbook(closed: list[dict]) -> None:
    """Promote repeated positive patterns; park repeated negatives as IGNORE."""
    playbook = load_json(PLAYBOOK, {}) or {}
    working = list(playbook.get("working") or [])
    ignore = list(playbook.get("ignore") or [])
    working_signals = {(w.get("signal") or "").lower() for w in working}
    ignore_signals = {(i.get("signal") or "").lower() for i in ignore}

    positives = [c for c in closed if c.get("verdict") == "positive"]
    negatives = [c for c in closed if c.get("verdict") == "negative"]

    for item in positives:
        signal = f"Impact+: {item.get('kind')} on {item.get('target')}"
        if signal.lower() in working_signals:
            continue
        working.append(
            {
                "signal": signal,
                "action": f"Repeat — {item.get('outcome')} after {item.get('title')}",
                "status": "working",
                "from_impact": True,
                "action_id": item.get("id"),
            }
        )
        working_signals.add(signal.lower())

    for item in negatives:
        signal = f"Impact-: {item.get('kind')} on {item.get('target')}"
        if signal.lower() in ignore_signals:
            continue
        # Only ignore if primary metric fell — don't ban experiments after one miss.
        ignore.append(
            {
                "signal": signal,
                "action": (
                    f"Revisit approach — {item.get('outcome')}. "
                    "Prefer kit-first distribution over repeating the same patch alone."
                ),
                "status": "ignore",
                "from_impact": True,
                "action_id": item.get("id"),
            }
        )
        ignore_signals.add(signal.lower())

    playbook["working"] = working[-40:]
    playbook["ignore"] = ignore[-40:]
    playbook["updated_at"] = now_utc()[:10]
    save_json(PLAYBOOK, playbook)


def impact_lesson_lines(closed: list[dict] | None = None, limit: int = 10) -> list[str]:
    log = load_log()
    items = closed if closed is not None else [
        a for a in (log.get("actions") or []) if a.get("status") == "completed"
    ]
    lines: list[str] = []
    for item in sorted(items, key=lambda a: a.get("measured_at") or a.get("executed_at") or "", reverse=True):
        lines.append(
            f"IMPACT [{item.get('verdict') or item.get('status')}]: "
            f"{item.get('kind')}:{item.get('target')} — {item.get('outcome') or 'pending'}"
        )
        if len(lines) >= limit:
            break
    measuring = sum(1 for a in (log.get("actions") or []) if a.get("status") == "measuring")
    if measuring:
        lines.insert(0, f"IMPACT: {measuring} action(s) still measuring (3-7d windows)")
    return lines


def format_impact_summary(closed: list[dict]) -> list[str]:
    lines: list[str] = []
    for item in closed:
        delta = item.get("delta") or {}
        parts = [f"{k} {v:+.0f}" for k, v in delta.items() if isinstance(v, (int, float))]
        summary = ", ".join(parts) if parts else "no delta"
        lines.append(
            f"{item.get('kind')}:{item.get('target')} [{item.get('verdict')}] "
            f"{item.get('outcome')} ({summary})"
        )
    return lines


def run_impact_cycle(applied: list[Any] | None = None) -> dict:
    """Score due actions, ingest retros, record today's applied list."""
    ingest_session_retros()
    backfill_shipped_surfaces()
    closed = measure_due_actions()
    recorded = record_actions(applied or [])
    return {
        "closed": closed,
        "recorded": recorded,
        "lessons": impact_lesson_lines(closed) + session_lesson_lines(8),
        "summary_lines": format_impact_summary(closed),
    }


def main() -> int:
    result = run_impact_cycle()
    print(f"Impact cycle: closed={len(result['closed'])} recorded={len(result['recorded'])}")
    for line in result["lessons"][:12]:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
