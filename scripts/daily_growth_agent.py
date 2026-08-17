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
    """Send growth summary when SMTP secrets exist; otherwise skip."""
    import os
    import smtplib
    from email.message import EmailMessage

    to_addr = (os.environ.get("GROWTH_REPORT_EMAIL") or "").strip()
    host = (os.environ.get("GROWTH_SMTP_HOST") or "").strip()
    user = (os.environ.get("GROWTH_SMTP_USER") or "").strip()
    password = (os.environ.get("GROWTH_SMTP_PASS") or "").strip()
    port = int(os.environ.get("GROWTH_SMTP_PORT") or "587")
    if not (to_addr and host and user and password):
        return "email skipped (missing GROWTH_* secrets)"
    body = summary_path.read_text(encoding="utf-8")
    msg = EmailMessage()
    msg["Subject"] = f"Sill Garden growth — {now_utc()[:10]}"
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
    return f"email sent to {to_addr}"


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

    learning = build_learning()
    metrics = metrics_from_latest()
    proposed = dedupe_proposed(propose_ctr_first_changes(metrics, max_items=8))
    auto = pick_auto_changes(proposed, max_items=MAX_CHANGES)
    applied = apply_changes(auto, dry_run=args.dry_run)

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
        "distribution": pack,
        "indexnow": index_result,
        "impact_lines": format_impact_lines(auto),
    }
    summary_path = write_daily_summary(payload)
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
    if pack_path:
        state["last_distribution"] = str(pack_path.relative_to(ROOT)).replace("\\", "/")
    save_json(STATE_PATH, state)

    print(f"Growth agent {'DRY RUN' if args.dry_run else 'OK'} · applied={len(applied)}")
    for line in applied:
        print(f"  - {line}")
    print(f"Summary: {summary_path}")
    print(f"Email: {email_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
