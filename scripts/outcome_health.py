#!/usr/bin/env python3
"""Outcome health — fail closed when the growth flywheel is spinning empty.

CI agents can succeed while sessions/views stay flat for weeks. This gate:

1. Reads analytics history for consecutive zero-session days
2. Flags flat YouTube lifetime views
3. Writes products/growth/outcome-health.json
4. Enqueues P0 acquisition actions when stalled
5. Emails an ALERT when stalled (SMTP or Resend)
6. Exits 1 on critical stall so GitHub notifies on workflow failure

  python scripts/outcome_health.py
  python scripts/outcome_health.py --email
  python scripts/outcome_health.py --warn-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_dotenv, load_json, now_utc, save_json
from board_actions import enqueue
from notify_email import send_email

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "products" / "analytics" / "latest.json"
HISTORY = ROOT / "products" / "analytics" / "history.json"
YT_STATE = ROOT / "products" / "youtube" / "publish-state.json"
DIST = ROOT / "products" / "growth" / "distribution" / "latest.json"
OUT = ROOT / "products" / "growth" / "outcome-health.json"

# Flat for this many calendar days of snapshots → critical
ZERO_SESSION_DAYS_CRITICAL = 3
# YouTube lifetime views unchanged across this many history points → warn
YT_FLAT_POINTS = 6
# Rolling sessions below this for many days also counts as stalled acquisition
LOW_SESSION_THRESHOLD = 5
LOW_SESSION_DAYS_CRITICAL = 7


def _as_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _sessions(entry: dict) -> int | None:
    if not isinstance(entry, dict):
        return None
    hero = entry.get("hero") if isinstance(entry.get("hero"), dict) else {}
    for key in ("sessions_7d", "ga4_sessions_7d", "sessions"):
        if hero.get(key) is not None:
            return _as_int(hero.get(key))
        if entry.get(key) is not None:
            return _as_int(entry.get(key))
    return None


def _yt_views(entry: dict) -> int | None:
    if not isinstance(entry, dict):
        return None
    hero = entry.get("hero") if isinstance(entry.get("hero"), dict) else {}
    if hero.get("youtube_views_total") is not None:
        return _as_int(hero.get("youtube_views_total"))
    if entry.get("youtube_views_total") is not None:
        return _as_int(entry.get("youtube_views_total"))
    return None


def analyze() -> dict:
    latest = load_json(LATEST, {}) or {}
    history = load_json(HISTORY, []) or []
    if not isinstance(history, list):
        history = []
    hero = latest.get("hero") or {}
    sessions = int(hero.get("sessions_7d") or 0)
    gsc_impr = int(hero.get("gsc_impressions_7d") or 0)
    gsc_clicks = int(hero.get("gsc_clicks_7d") or 0)
    aff = int(hero.get("affiliate_clicks_7d") or 0)
    yt_views = int(hero.get("youtube_views_total") or 0)
    yt_sess = int(hero.get("youtube_sessions_7d") or 0)

    zero_days: list[str] = []
    seen_days: set[str] = set()
    for entry in reversed(history):
        day = str(entry.get("generated_at") or entry.get("date") or "")[:10]
        if not day or day in seen_days:
            continue
        seen_days.add(day)
        sess = _sessions(entry)
        if sess is None:
            continue
        if sess == 0:
            zero_days.append(day)
        else:
            break
    if sessions == 0 and now_utc()[:10] not in zero_days:
        zero_days.insert(0, now_utc()[:10])

    low_days: list[str] = []
    seen_low: set[str] = set()
    for entry in reversed(history):
        day = str(entry.get("generated_at") or entry.get("date") or "")[:10]
        if not day or day in seen_low:
            continue
        seen_low.add(day)
        sess = _sessions(entry)
        if sess is None:
            continue
        if sess < LOW_SESSION_THRESHOLD:
            low_days.append(day)
        else:
            break

    yt_series: list[tuple[str, int]] = []
    seen_yt: set[str] = set()
    for entry in reversed(history):
        day = str(entry.get("generated_at") or "")[:10]
        if not day or day in seen_yt:
            continue
        seen_yt.add(day)
        views = _yt_views(entry)
        if views is None:
            continue
        yt_series.append((day, views))
        if len(yt_series) >= YT_FLAT_POINTS:
            break
    yt_flat = len(yt_series) >= 3 and len({v for _, v in yt_series}) == 1

    yt_state = load_json(YT_STATE, {}) or {}
    next_eligible = yt_state.get("next_eligible_date")
    dist = load_json(DIST, {}) or {}
    dist_target = (dist.get("target") or {}).get("url") or ""

    stalled = (sessions == 0 and len(zero_days) >= ZERO_SESSION_DAYS_CRITICAL) or (
        sessions < LOW_SESSION_THRESHOLD and len(low_days) >= LOW_SESSION_DAYS_CRITICAL
    )
    severity = "critical" if stalled else ("warn" if sessions == 0 or yt_flat or sessions < LOW_SESSION_THRESHOLD else "ok")

    reasons: list[str] = []
    if sessions == 0:
        reasons.append(f"GA4 sessions_7d=0 for {len(zero_days)} calendar day(s)")
    elif sessions < LOW_SESSION_THRESHOLD:
        reasons.append(
            f"GA4 sessions_7d={sessions} (<{LOW_SESSION_THRESHOLD}) for {len(low_days)} day(s)"
        )
    if gsc_impr and not gsc_clicks:
        reasons.append(f"GSC {gsc_impr} impressions / 0 clicks")
    if yt_flat:
        reasons.append(f"YouTube lifetime views flat at {yt_views} across {len(yt_series)} days")
    if yt_sess == 0 and yt_views:
        reasons.append("YouTube -> site sessions = 0")
    if aff == 0:
        reasons.append("Affiliate clicks_7d = 0")

    actions = [
        "Post 1 Reddit value thread today (use products/growth/distribution/latest.json)",
        "Request indexing in GSC for any not-indexed guides (traffic action-queue P1)",
        "Publish next long-form YouTube only if title matches a live GSC query",
        "Do not ship more thin guides until sessions_7d > 0",
    ]

    return {
        "generated_at": now_utc(),
        "severity": severity,
        "stalled": stalled,
        "zero_session_days": zero_days,
        "zero_session_day_count": len(zero_days),
        "low_session_days": low_days,
        "low_session_day_count": len(low_days),
        "youtube_flat": yt_flat,
        "metrics": {
            "sessions_7d": sessions,
            "gsc_impressions_7d": gsc_impr,
            "gsc_clicks_7d": gsc_clicks,
            "affiliate_clicks_7d": aff,
            "youtube_views_total": yt_views,
            "youtube_sessions_7d": yt_sess,
            "next_eligible_date": next_eligible,
            "distribution_url": dist_target,
        },
        "reasons": reasons,
        "actions": actions,
        "thresholds": {
            "zero_session_days_critical": ZERO_SESSION_DAYS_CRITICAL,
            "low_session_threshold": LOW_SESSION_THRESHOLD,
            "low_session_days_critical": LOW_SESSION_DAYS_CRITICAL,
            "youtube_flat_points": YT_FLAT_POINTS,
        },
    }


def enqueue_stall_actions(report: dict) -> None:
    if not report.get("stalled"):
        return
    enqueue(
        role="cmo",
        action_type="acquisition_stall",
        title="ALERT: zero sessions for 5+ days — distribute manually",
        detail=(
            "Automation is healthy but acquisition is dead. "
            + " | ".join(report.get("reasons") or [])
            + ". Post Reddit/Pinterest from distribution/latest.json today."
        ),
        target="acquisition",
        auto=False,
        priority="P0",
    )


def render_email(report: dict) -> str:
    m = report.get("metrics") or {}
    lines = [
        f"Sill Garden outcome health — {report.get('severity', '').upper()}",
        f"Generated: {report.get('generated_at')}",
        "",
        "Why this fired:",
    ]
    lines.extend(f"- {r}" for r in (report.get("reasons") or ["(none)"]))
    lines.extend(
        [
            "",
            "Metrics:",
            f"- sessions_7d: {m.get('sessions_7d')}",
            f"- gsc: {m.get('gsc_impressions_7d')} impr / {m.get('gsc_clicks_7d')} clicks",
            f"- affiliate_clicks_7d: {m.get('affiliate_clicks_7d')}",
            f"- youtube views: {m.get('youtube_views_total')} · YT→site: {m.get('youtube_sessions_7d')}",
            f"- next YT eligible: {m.get('next_eligible_date')}",
            f"- distribute: {m.get('distribution_url')}",
            "",
            "Do this today:",
        ]
    )
    lines.extend(f"- {a}" for a in (report.get("actions") or []))
    lines.extend(
        [
            "",
            "Dashboard: http://127.0.0.1:8793/dashboard",
            "Site: https://sillgarden.com",
            "",
            "This alert exists so green CI cannot hide a flat growth loop again.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Sill Garden outcome health gate")
    parser.add_argument("--email", action="store_true", help="Email when warn/critical")
    parser.add_argument("--force-email", action="store_true")
    parser.add_argument("--warn-only", action="store_true", help="Never exit 1")
    args = parser.parse_args()

    report = analyze()
    save_json(OUT, report)
    if report.get("stalled"):
        try:
            enqueue_stall_actions(report)
        except Exception as exc:  # noqa: BLE001
            print(f"queue enqueue failed: {exc}", file=sys.stderr)

    print(f"outcome health: {report['severity']} · zero_days={report['zero_session_day_count']}")
    for reason in report.get("reasons") or []:
        print(f"  - {reason}")

    should_mail = args.force_email or (args.email and report["severity"] in ("warn", "critical"))
    if should_mail:
        subject = (
            f"ALERT: Sill Garden growth stalled ({report['severity']})"
            if report["severity"] != "ok"
            else f"Sill Garden outcome health OK — {now_utc()[:10]}"
        )
        result = send_email(subject=subject, body=render_email(report))
        print(f"email: {result}")
        report["email"] = result
        save_json(OUT, report)

    if report.get("stalled") and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
