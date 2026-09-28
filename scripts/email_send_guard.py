#!/usr/bin/env python3
"""Cross-channel email rate limit + duplicate-body guard (MTS-compatible)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

CHANNEL_RULES: dict[str, dict[str, float]] = {
    "sill-growth": {"min_hours": 20.0, "dedup_hours": 48.0},
    "sill-exec-board": {"min_hours": 144.0, "dedup_hours": 168.0},
    "sill-outcome": {"min_hours": 12.0, "dedup_hours": 24.0},
    "oauth-alert": {"min_hours": 6.0, "dedup_hours": 12.0},
}

CROSS_SKIP: list[tuple[str, str, float]] = [
    ("sill-growth", "sill-outcome", 6.0),
]

_NOISE_LINE = re.compile(
    r"(snapshot|generated|sill garden ·|run #|_gsc window|sent via:|"
    r"\d{1,2}:\d{2}\s*(il|israel|utc)|^# sill)",
    re.I,
)

ROOT = Path(__file__).resolve().parents[1]


def _ledger_path() -> Path:
    env = (os.environ.get("EMAIL_LEDGER_PATH") or "").strip()
    if env:
        return Path(env)
    return ROOT / "products" / "growth" / "email-send-ledger.json"


def _load_ledger() -> dict:
    path = _ledger_path()
    if not path.is_file():
        return {"sends": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"sends": []}


def _save_ledger(data: dict) -> None:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["sends"] = (data.get("sends") or [])[-200:]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _parse_ts(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _hours_since(ts: str) -> float | None:
    dt = _parse_ts(ts)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0


def normalize_body(body: str) -> str:
    lines: list[str] = []
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _NOISE_LINE.search(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def body_fingerprint(body: str) -> str:
    return hashlib.sha256(normalize_body(body).encode("utf-8")).hexdigest()[:16]


def is_force_send() -> bool:
    for key in ("EMAIL_SEND_FORCE", "GROWTH_EMAIL_FORCE"):
        if os.environ.get(key, "").strip().lower() in ("1", "true", "yes"):
            return True
    return False


def should_send_email(
    channel: str,
    subject: str,
    body: str,
    *,
    force: bool = False,
) -> tuple[bool, str]:
    if force or is_force_send():
        return True, "forced"

    rules = CHANNEL_RULES.get(channel)
    if not rules:
        return True, "no rules for channel"

    fp = body_fingerprint(body)
    ledger = _load_ledger()
    sends = ledger.get("sends") or []
    min_hours = float(rules.get("min_hours", 0))
    dedup_hours = float(rules.get("dedup_hours", 0))

    for row in reversed(sends):
        if row.get("channel") != channel:
            continue
        hours = _hours_since(row.get("sent_at", ""))
        if hours is None:
            continue
        if hours < min_hours:
            return False, f"{channel}: last send {hours:.1f}h ago (min {min_hours:.0f}h)"
        break

    for row in reversed(sends):
        if row.get("channel") != channel:
            continue
        if row.get("body_fp") != fp:
            continue
        hours = _hours_since(row.get("sent_at", ""))
        if hours is not None and hours < dedup_hours:
            return False, f"{channel}: identical content {hours:.1f}h ago"
        break

    for target, blocker, hours_limit in CROSS_SKIP:
        if channel != target:
            continue
        for row in reversed(sends):
            if row.get("channel") != blocker:
                continue
            hours = _hours_since(row.get("sent_at", ""))
            if hours is not None and hours < hours_limit:
                return False, (
                    f"{channel}: skipped — {blocker} email {hours:.1f}h ago "
                    f"(overlap window {hours_limit:.0f}h)"
                )
            break

    return True, "ok"


def record_email_send(
    channel: str,
    subject: str,
    body: str,
    *,
    recipient: str = "",
    via: str = "",
) -> None:
    ledger = _load_ledger()
    ledger.setdefault("sends", []).append(
        {
            "channel": channel,
            "subject": (subject or "")[:120],
            "body_fp": body_fingerprint(body),
            "recipient": recipient[:80],
            "via": via[:80],
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save_ledger(ledger)
