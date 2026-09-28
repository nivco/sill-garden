#!/usr/bin/env python3
"""Daily growth agent for Sill Garden — learn, apply safe SEO, draft distribution.

  python scripts/daily_growth_agent.py --dry-run
  python scripts/daily_growth_agent.py --refresh
  python scripts/daily_growth_agent.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_dotenv, load_json, now_utc, save_json
from board_actions import (
    dedupe_proposed,
    enqueue,
    format_impact_lines,
    load_queue,
    pick_auto_changes,
    record_applied,
    save_queue,
    sync_manual_to_traffic_queue,
)
from ctr_first_optimizer import propose_ctr_first_changes
from growth_actions import (
    build_distribution_pack,
    metrics_from_latest,
    ping_indexnow,
    save_distribution_pack,
    write_daily_summary,
)
from guide_content import patch_guide_seo
from metrics_learning import build_learning
from action_impact_learning import (
    hero_metrics,
    impact_lesson_lines,
    session_lesson_lines,
)

ROOT = Path(__file__).resolve().parents[1]
GROWTH = ROOT / "products" / "growth"
STATE_PATH = GROWTH / "daily-agent-state.json"
MAX_CHANGES = 3


def run_analytics() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "analytics_summary.py")],
        cwd=str(ROOT),
        check=False,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "traffic_optimizer.py")],
        cwd=str(ROOT),
        check=False,
    )


def apply_changes(changes: list[dict], *, dry_run: bool) -> list[str]:
    applied: list[str] = []
    queue = load_queue()
    for change in changes:
        if change.get("type") != "tune_guide_seo":
            continue
        slug = change.get("slug")
        title = change.get("title_patch")
        description = change.get("description_patch")
        label = f"tune_guide_seo:{slug} — {change.get('reason')}"
        if dry_run:
            applied.append(f"[dry-run] {label}")
            continue
        doc = patch_guide_seo(slug, title=title, description=description)
        if doc:
            applied.append(label)
            record_applied(queue, change)
        else:
            applied.append(f"[skip unchanged] {label}")
    return applied


def maybe_send_email(summary_path: Path, payload: dict) -> str:
    """Send MTS-style unified growth email (Resend/Buttondown/SMTP + guards)."""
    from growth_report_builder import build_unified_growth_email
    from growth_report_email import send_growth_report

    report = build_unified_growth_email(
        header_title="Sill Garden Traffic & Growth Summary",
        applied=payload.get("applied") or [],
        learnings=payload.get("learnings") or [],
        outcome=payload.get("outcome_health") or {},
        distribution=payload.get("distribution") or {},
    )
    reports_dir = GROWTH / "daily-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    save_json(reports_dir / f"{report['date']}.json", report)
    # Keep markdown summary as the human-readable archive; email uses unified body.
    summary_path.write_text(report["email_body"] + "\n", encoding="utf-8")
    result = send_growth_report(
        report["email_subject"],
        report["email_body"],
        dry_run=False,
        channel="sill-growth",
    )
    if result.get("ok"):
        return f"email sent via {result.get('via')} ({result.get('detail')})"
    if result.get("skipped"):
        return f"email skipped: {result.get('detail')}"
    return f"email failed: {result.get('detail')}"


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Sill Garden daily growth agent")
    parser.add_argument("--refresh", action="store_true", help="Refresh analytics first")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-indexnow", action="store_true")
    parser.add_argument("--skip-email", action="store_true")
    args = parser.parse_args()

    if args.refresh:
        run_analytics()

    from outcome_health import analyze as analyze_outcome
    from competitive_learning import run_competitive_learning

    learning = build_learning()
    # Fold session retros (how we decided) into the daily learning set.
    for line in session_lesson_lines(10):
        if line not in (learning.get("learnings") or []):
            learning.setdefault("learnings", []).insert(0, line)

    metrics = metrics_from_latest()
    outcome = analyze_outcome()

    # Score prior actions / ingest session retros before applying new ones.
    impact: dict = {"closed": [], "recorded": [], "lessons": [], "summary_lines": []}
    if not args.dry_run:
        try:
            from action_impact_learning import measure_due_actions, ingest_session_retros

            ingest_session_retros()
            closed = measure_due_actions(metrics=hero_metrics())
            impact["closed"] = closed
            impact["lessons"] = impact_lesson_lines(closed) + session_lesson_lines(8)
            impact["summary_lines"] = [
                f"{c.get('kind')}:{c.get('target')} [{c.get('verdict')}] {c.get('outcome')}"
                for c in closed
            ]
            for line in impact["lessons"]:
                if line not in (learning.get("learnings") or []):
                    learning.setdefault("learnings", []).insert(0, line)
        except Exception as exc:  # noqa: BLE001
            print(f"impact learning failed: {exc}", file=sys.stderr)

    competitive = {"learnings": [], "proposed_actions": []}
    try:
        competitive = run_competitive_learning(max_peers=5, include_llm=True)
        for line in competitive.get("learnings") or []:
            if line not in (learning.get("learnings") or []):
                learning.setdefault("learnings", []).insert(0, line)
        learning["learnings"] = (learning.get("learnings") or [])[:24]
        if not args.dry_run:
            from metrics_learning import OUT as LEARNING_OUT

            snap = dict(learning)
            snap["competitive"] = {
                "ok_peers": competitive.get("ok_peers"),
                "generated_at": competitive.get("generated_at"),
            }
            snap["impact"] = {
                "closed_today": len(impact.get("closed") or []),
                "lessons": (impact.get("lessons") or [])[:8],
            }
            save_json(LEARNING_OUT, snap)
    except Exception as exc:  # noqa: BLE001
        competitive = {"error": str(exc)[:200], "learnings": []}
        print(f"competitive learning failed: {exc}", file=sys.stderr)

    proposed = dedupe_proposed(propose_ctr_first_changes(metrics, max_items=8))
    auto = pick_auto_changes(proposed, max_items=MAX_CHANGES)
    applied = apply_changes(auto, dry_run=args.dry_run)

    # Content + visuality iteration from peer learning
    if not args.dry_run:
        try:
            from visual_content_iteration import apply_iterations

            vis = apply_iterations(dry_run=False)
            applied.extend(vis.get("applied") or [])
        except Exception as exc:  # noqa: BLE001
            applied.append(f"visual_iteration failed: {exc}")
            print(f"visual iteration failed: {exc}", file=sys.stderr)

    manual = [p for p in proposed if p not in auto]
    for item in manual:
        enqueue(
            role="seo",
            action_type=item.get("type") or "manual",
            title=f"{item.get('type')}: {item.get('slug')}",
            detail=item.get("reason") or "",
            target=item.get("slug") or "",
            auto=False,
            priority="P1",
        )

    if outcome.get("stalled") and not args.dry_run:
        enqueue(
            role="cmo",
            action_type="acquisition_stall",
            title="ALERT: zero sessions for 5+ days — distribute manually",
            detail=" | ".join(outcome.get("reasons") or []) or "sessions flat",
            target="acquisition",
            auto=False,
            priority="P0",
        )
        applied.append("outcome_health: stalled → P0 acquisition enqueued")

    pack = build_distribution_pack(metrics)
    pack_path = None
    if not args.dry_run:
        pack_path = save_distribution_pack(pack)
        sync_manual_to_traffic_queue()

    index_result = {"skipped": True}
    if not args.dry_run and not args.skip_indexnow:
        index_result = ping_indexnow()
        if index_result.get("ok"):
            applied.append("IndexNow ping")

    # Record today's actions with metric baselines for 3–7d impact scoring.
    if not args.dry_run:
        try:
            from action_impact_learning import record_actions

            to_record: list = list(auto) + [
                {"type": "distribution", "target": (pack.get("target") or {}).get("slug") or "pack",
                 "title": "kit-first distribution pack", "primary_metric": "sessions_7d"}
            ]
            for line in applied:
                if isinstance(line, str):
                    to_record.append(line)
            impact["recorded"] = record_actions(to_record, metrics=hero_metrics())
            if impact.get("closed"):
                applied.append(f"impact scored {len(impact['closed'])} prior action(s)")
        except Exception as exc:  # noqa: BLE001
            applied.append(f"impact record failed: {exc}")

    payload = {
        "generated_at": now_utc(),
        "dry_run": args.dry_run,
        "applied": applied,
        "proposed": [
            {
                "type": p.get("type"),
                "title": p.get("slug"),
                "detail": p.get("reason"),
                "reason": p.get("reason"),
            }
            for p in proposed
        ],
        "learnings": learning.get("learnings") or [],
        "competitive": {
            "ok_peers": competitive.get("ok_peers"),
            "peer_count": competitive.get("peer_count"),
            "learnings": (competitive.get("learnings") or [])[:6],
            "actions": competitive.get("proposed_actions") or [],
        },
        "distribution": pack,
        "indexnow": index_result,
        "impact_lines": (impact.get("summary_lines") or []) + format_impact_lines(auto),
        "impact": {
            "closed": len(impact.get("closed") or []),
            "recorded": len(impact.get("recorded") or []),
            "lessons": (impact.get("lessons") or [])[:8],
        },
        "outcome_health": outcome,
    }
    summary_path = write_daily_summary(payload)
    if not args.dry_run:
        save_json(GROWTH / "outcome-health.json", outcome)

    email_status = "email skipped"
    if not args.dry_run and not args.skip_email:
        try:
            email_status = maybe_send_email(summary_path, payload)
        except Exception as exc:  # noqa: BLE001
            email_status = f"email failed: {exc}"

    state = load_json(STATE_PATH, {}) or {}
    state["last_run"] = now_utc()
    state["last_applied"] = applied
    state["last_summary"] = str(summary_path.relative_to(ROOT)).replace("\\", "/")
    state["last_outcome_severity"] = outcome.get("severity")
    state["last_impact"] = {
        "closed": len(impact.get("closed") or []),
        "recorded": len(impact.get("recorded") or []),
    }
    if pack_path:
        state["last_distribution"] = str(pack_path.relative_to(ROOT)).replace("\\", "/")
    save_json(STATE_PATH, state)

    print(f"Growth agent {'DRY RUN' if args.dry_run else 'OK'} · applied={len(applied)}")
    for line in applied:
        print(f"  - {line}")
    if impact.get("summary_lines"):
        print("Impact:")
        for line in impact["summary_lines"][:6]:
            print(f"  - {line}")
    print(f"Outcome: {outcome.get('severity')} · zero_days={outcome.get('zero_session_day_count')}")
    print(f"Summary: {summary_path}")
    print(f"Email: {email_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
