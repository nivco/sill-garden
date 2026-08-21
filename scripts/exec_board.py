#!/usr/bin/env python3
"""Executive Board orchestrator for Sill Garden.

Runs per-role diagnosis on a cadence (daily/weekly/monthly), grounded in the
real analytics snapshot (products/analytics/latest.json). Writes an auditable
trail under reports/board/.

Usage:
  python scripts/exec_board.py                 # auto-detect cadence from date
  python scripts/exec_board.py --cadence weekly
  python scripts/exec_board.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_json
from board_actions import (
    _metrics_slice,
    build_queue_items,
    format_impact_lines,
    format_queue_section,
    load_queue,
    measure_impacts,
    merge_queue,
    save_queue,
    sync_manual_to_traffic_queue,
)

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS_LATEST = ROOT / "products" / "analytics" / "latest.json"
REPORTS = ROOT / "reports" / "board"
CHANGELOG = REPORTS / "CHANGELOG.md"
KPI_LEDGER = REPORTS / "kpi-ledger.csv"

CADENCE_ROLES = {
    "daily": ["seo", "data", "cmo"],
    "weekly": ["ceo", "cmo", "seo", "content", "cro", "data", "cto"],
    "monthly": ["ceo", "cmo", "seo", "content", "cro", "data", "cto"],
}

ROLE_TITLES = {
    "ceo": "CEO / Strategy",
    "cmo": "CMO / Growth & Distribution",
    "seo": "Head of SEO",
    "content": "Head of Content / Editorial",
    "cro": "Head of CRO / Monetization",
    "data": "Head of Data / Analytics",
    "cto": "CTO / Engineering",
}


def _num(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def detect_cadence(today: date) -> str:
    if today.day == 1:
        return "monthly"
    if today.weekday() == 0:
        return "weekly"
    return "daily"


def load_snapshot() -> tuple[dict, dict]:
    latest = load_json(ANALYTICS_LATEST, {}) or {}
    hero = latest.get("hero") or latest.get("snapshot") or {}
    sources = latest.get("sources") or {}
    return hero, sources


def diagnose_seo(s: dict) -> dict:
    impr = _num(s.get("gsc_impressions_7d"), 0) or 0
    clicks = _num(s.get("gsc_clicks_7d"), 0) or 0
    pos = _num(s.get("gsc_avg_position_7d"))
    ctr = (clicks / impr * 100) if impr else 0.0
    actions, findings = [], []
    if impr and clicks == 0:
        findings.append(f"{int(impr)} impressions but 0 clicks (7d)")
        actions.append(
            "Rewrite titles/meta on top impression guides for CTR; add SERP hooks (2026, apartment, beginners)."
        )
    elif impr:
        findings.append(
            f"{int(impr)} impr · {int(clicks)} clicks · CTR {ctr:.1f}% · avg pos {pos if pos is not None else 'n/a'}"
        )
    else:
        findings.append("No GSC impressions — verify indexing/coverage.")
        actions.append("Confirm key guides indexed; resubmit sitemap; request indexing for priority pages.")
    if pos is not None and pos > 20:
        actions.append("Deepen topical authority + internal links to push head terms toward page 1.")
    return {
        "diagnosis": "; ".join(findings),
        "actions": actions or ["Hold — monitor impressions/position."],
        "metrics": [
            f"impressions_7d={int(impr)}",
            f"clicks_7d={int(clicks)}",
            f"avg_position_7d={pos if pos is not None else 'n/a'}",
        ],
        "next": "Pick the highest-impression low-CTR guide and ship a title/meta test.",
        "kpis": [
            {"metric": "gsc_impressions_7d", "value": int(impr), "source": "analytics/latest.json"},
            {"metric": "gsc_clicks_7d", "value": int(clicks), "source": "analytics/latest.json"},
        ],
    }


def diagnose_cmo(s: dict) -> dict:
    ga4 = _num(s.get("sessions_7d") or s.get("ga4_sessions_7d"), 0) or 0
    yt_sessions = _num(s.get("youtube_sessions_7d"), 0) or 0
    actions, findings = [], []
    findings.append(f"{int(ga4)} GA4 sessions (7d) · {int(yt_sessions)} from YouTube")
    if ga4 < 50:
        actions.append(
            "Low real sessions — prioritize YouTube videos, Reddit value-first posts, and social distribution."
        )
    elif yt_sessions < 5:
        actions.append("Keep daily YouTube public uploads; refresh descriptions with UTM guide links.")
    return {
        "diagnosis": "; ".join(findings),
        "actions": actions or ["Distribution steady — maintain cadence, pursue 1 backlink/partnership."],
        "metrics": [f"ga4_sessions_7d={int(ga4)}", f"youtube_sessions_7d={int(yt_sessions)}"],
        "next": "Ship one distribution asset linking a money guide.",
        "kpis": [
            {"metric": "ga4_sessions_7d", "value": int(ga4), "source": "analytics/latest.json"},
        ],
    }


def diagnose_data(s: dict, sources: dict) -> dict:
    actions, findings = [], []
    broken = []
    for name in ("ga4", "gsc"):
        if (sources.get(name) or {}).get("error"):
            broken.append(name.upper())
    if broken:
        findings.append(f"OAuth/source errors: {', '.join(broken)}")
        actions.append("Refresh Google analytics OAuth so metrics stay live.")
    else:
        findings.append("Core sources (GA4/GSC) reporting; snapshot fresh.")
    if s.get("affiliate_clicks_7d") is None:
        actions.append("Verify affiliate click tracking (GA4 affiliate_click event).")
    return {
        "diagnosis": "; ".join(findings),
        "actions": actions or ["Measurement healthy — extend KPI ledger trendlines."],
        "metrics": [f"sources_ok={not broken}"],
        "next": "Verify next snapshot has no source errors.",
        "kpis": [],
    }


def diagnose_content(s: dict) -> dict:
    from guide_content import load_guides

    n_guides = len(load_guides())
    return {
        "diagnosis": f"{n_guides} guides published; review freshness on flagship pages.",
        "actions": [
            "Refresh top guide with current pricing/verdict and stamp updatedDate.",
            "Add FAQ sections to guides matching early GSC queries.",
        ],
        "metrics": [f"guides={n_guides}"],
        "next": "Update one flagship guide and confirm it gets re-indexed.",
        "kpis": [{"metric": "guides_count", "value": n_guides, "source": "src/content/guides/"}],
    }


def diagnose_cro(s: dict) -> dict:
    aff_7d = _num(s.get("affiliate_clicks_7d"), 0) or 0
    actions, findings = [], []
    findings.append(f"Affiliate clicks 7d={int(aff_7d)}")
    if aff_7d == 0:
        actions.append(
            "Raise affiliate CTR: above-the-fold verdict CTA + comparison-table outbound links on money guides."
        )
    return {
        "diagnosis": "; ".join(findings),
        "actions": actions or ["Monetization steady — A/B one CTA placement."],
        "metrics": [f"affiliate_clicks_7d={int(aff_7d)}"],
        "next": "Add/adjust one high-intent CTA on the best-ranked guide.",
        "kpis": [
            {"metric": "affiliate_clicks_7d", "value": int(aff_7d), "source": "analytics/latest.json"},
        ],
    }


def diagnose_cto(s: dict) -> dict:
    return {
        "diagnosis": "Astro static build + Cloudflare Pages; automation workflows are the surface.",
        "actions": [
            "Keep Astro build green; ensure all scheduled workflows succeed (check Actions).",
            "Spot-check Core Web Vitals on flagship guides.",
        ],
        "metrics": [],
        "next": "Confirm latest workflow runs are green; no build regressions.",
        "kpis": [],
    }


def diagnose_ceo(role_outputs: dict) -> dict:
    quick_wins = []
    for rid, out in role_outputs.items():
        if rid == "ceo":
            continue
        for a in out.get("actions", [])[:1]:
            quick_wins.append(f"[{ROLE_TITLES[rid]}] {a}")
    return {
        "diagnosis": "Synthesized board priorities; enforce focus on measurable, reversible wins.",
        "actions": quick_wins[:5] or ["No threshold breaches this cycle — maintain cadence."],
        "metrics": [f"active_roles={len(role_outputs)}"],
        "next": "Lock this cycle's 3-item execution set and verify prior 'pending' metrics.",
        "kpis": [],
    }


def run_role(rid: str, snapshot: dict, sources: dict, role_outputs: dict) -> dict:
    if rid == "seo":
        return diagnose_seo(snapshot)
    if rid == "cmo":
        return diagnose_cmo(snapshot)
    if rid == "data":
        return diagnose_data(snapshot, sources)
    if rid == "content":
        return diagnose_content(snapshot)
    if rid == "cro":
        return diagnose_cro(snapshot)
    if rid == "cto":
        return diagnose_cto(snapshot)
    if rid == "ceo":
        return diagnose_ceo(role_outputs)
    return {"diagnosis": "n/a", "actions": [], "metrics": [], "next": "", "kpis": []}


def build_report_md(cadence: str, today: str, role_outputs: dict, snapshot: dict) -> str:
    lines = [
        f"# Executive Board — {cadence.title()} iteration · {today}",
        "",
        f"Generated by `scripts/exec_board.py` · cadence **{cadence}**",
        "",
    ]
    if cadence in ("weekly", "monthly"):
        lines += [
            "## Executive summary",
            f"- Sessions (7d): {snapshot.get('sessions_7d') or snapshot.get('ga4_sessions_7d', 'n/a')} · "
            f"GSC impr: {snapshot.get('gsc_impressions_7d', 'n/a')} · "
            f"clicks: {snapshot.get('gsc_clicks_7d', 'n/a')}",
            f"- Focus next cycle: {role_outputs.get('ceo', {}).get('next', 'n/a')}",
            "",
        ]
    lines.append("## Per-role iteration log")
    lines.append("")
    for rid, out in role_outputs.items():
        lines.append(f"### {ROLE_TITLES[rid]}")
        lines.append(f"- **Diagnosis:** {out['diagnosis']}")
        if out["actions"]:
            lines.append("- **Actions:**")
            for a in out["actions"]:
                lines.append(f"  - {a}")
        lines.append(f"- **Metrics:** {', '.join(out['metrics']) if out['metrics'] else 'no data'}")
        lines.append(f"- **Next:** {out['next']}")
        lines.append("")
    return "\n".join(lines)


def send_board_email(
    cadence: str,
    today: str,
    body: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    import smtplib
    from email.message import EmailMessage

    to_addr = (os.environ.get("GROWTH_REPORT_EMAIL") or "").strip()
    host = (os.environ.get("GROWTH_SMTP_HOST") or "").strip()
    user = (os.environ.get("GROWTH_SMTP_USER") or "").strip()
    password = (os.environ.get("GROWTH_SMTP_PASS") or "").strip()
    port = int(os.environ.get("GROWTH_SMTP_PORT") or "587")
    if not (to_addr and host and user and password):
        return {"via": "skipped", "reason": "missing GROWTH_* secrets"}
    if dry_run:
        return {"via": "dry-run", "to": to_addr}
    msg = EmailMessage()
    msg["Subject"] = f"Sill Garden · Board ({cadence}) — {today}"
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
    return {"via": "smtp", "to": to_addr}


def should_send_email(cadence: str, send_email: bool, skip_email: bool) -> bool:
    if skip_email:
        return False
    if send_email:
        return True
    return cadence in ("weekly", "monthly")


def append_changelog(cadence: str, today: str, role_outputs: dict) -> None:
    CHANGELOG.parent.mkdir(parents=True, exist_ok=True)
    if not CHANGELOG.is_file():
        CHANGELOG.write_text("# Executive Board — Changelog\n\n", encoding="utf-8")
    top_action = (role_outputs.get("ceo", {}).get("actions") or ["n/a"])[0]
    line = f"- {today} · {cadence} · roles={len(role_outputs)} · top: {top_action}\n"
    with CHANGELOG.open("a", encoding="utf-8") as f:
        f.write(line)


def append_kpi_ledger(cadence: str, today: str, role_outputs: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    new_file = not KPI_LEDGER.is_file()
    with KPI_LEDGER.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "cadence", "role", "metric", "value", "source"])
        for rid, out in role_outputs.items():
            for kpi in out.get("kpis", []):
                w.writerow([today, cadence, rid, kpi["metric"], kpi["value"], kpi["source"]])


def main() -> int:
    parser = argparse.ArgumentParser(description="Sill Garden Executive Board loop")
    parser.add_argument("--cadence", choices=["daily", "weekly", "monthly"], default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--send-email", action="store_true")
    parser.add_argument("--skip-email", action="store_true")
    parser.add_argument("--force-email", action="store_true")
    parser.add_argument("--email-only", action="store_true")
    args = parser.parse_args()

    today_d = datetime.now(timezone.utc).date()
    today = today_d.isoformat()
    cadence = args.cadence or detect_cadence(today_d)
    report_path = REPORTS / f"{today}-{cadence}.md"

    if args.email_only:
        if not report_path.is_file():
            print(
                f"No report at {report_path.relative_to(ROOT)} — run without --email-only first.",
                file=sys.stderr,
            )
            return 1
        body = report_path.read_text(encoding="utf-8")
        try:
            result = send_board_email(
                cadence, today, body, force=args.force_email, dry_run=args.dry_run
            )
        except RuntimeError as exc:
            print(f"Email failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2))
        return 0

    snapshot, sources = load_snapshot()
    if not snapshot:
        print(
            "WARNING: no analytics snapshot found. "
            "Roles will report 'no data'. Run scripts/analytics_summary.py first.",
            file=sys.stderr,
        )

    role_outputs: dict[str, dict] = {}
    for rid in CADENCE_ROLES[cadence]:
        if rid == "ceo":
            continue
        role_outputs[rid] = run_role(rid, snapshot, sources, role_outputs)
    if "ceo" in CADENCE_ROLES[cadence]:
        ceo = run_role("ceo", snapshot, sources, role_outputs)
        role_outputs = {"ceo": ceo, **role_outputs}

    report_md = build_report_md(cadence, today, role_outputs, snapshot)

    queue = load_queue()
    closed = measure_impacts(queue, _metrics_slice(snapshot), today) if not args.dry_run else []
    added = 0
    if not args.dry_run:
        added = merge_queue(queue, build_queue_items(snapshot, role_outputs, cadence))
        save_queue(queue)
        sync_manual_to_traffic_queue(queue)
    report_md += "\n\n" + format_queue_section(queue)
    if closed:
        report_md += "\n\n**Impacts closed this run:**\n" + "\n".join(
            f"- {line}" for line in format_impact_lines(closed)
        )

    if args.dry_run:
        print(report_md)
        print("\n[dry-run] No files written.")
        return 0

    REPORTS.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")
    append_changelog(cadence, today, role_outputs)
    append_kpi_ledger(cadence, today, role_outputs)

    print(f"Executive Board ({cadence}) -> {report_path.relative_to(ROOT)}")
    print(f"  roles: {', '.join(role_outputs)}")
    print(f"  action queue: +{added} items, closed {len(closed)} experiments")

    if should_send_email(cadence, args.send_email, args.skip_email):
        try:
            result = send_board_email(cadence, today, report_md, force=args.force_email)
            print(f"  email: {result.get('via', result)}")
        except RuntimeError as exc:
            print(f"  email FAILED (report saved): {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
