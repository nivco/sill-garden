#!/usr/bin/env python3
"""Quiet hours for outbound email — Israel local time only.

Allowed window: 08:00–23:00 Asia/Jerusalem (inclusive of 08:00, exclusive of 23:00).
Mirrors Maker Tool Stack operational policy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IL = ZoneInfo("Asia/Jerusalem")
EMAIL_WINDOW_START_MINUTES = 8 * 60
EMAIL_WINDOW_END_MINUTES = 23 * 60


def now_israel(now: datetime | None = None) -> datetime:
    if now is None:
        now = datetime.now(tz=timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(IL)


def israel_email_window_status(now: datetime | None = None) -> tuple[bool, str]:
    local = now_israel(now)
    mins = local.hour * 60 + local.minute
    stamp = local.strftime("%H:%M %Z")
    if EMAIL_WINDOW_START_MINUTES <= mins < EMAIL_WINDOW_END_MINUTES:
        return True, f"within Israel email window ({stamp})"
    return False, (
        f"quiet hours Israel ({stamp}); send only "
        f"{EMAIL_WINDOW_START_MINUTES // 60:02d}:00-"
        f"{EMAIL_WINDOW_END_MINUTES // 60:02d}:00 Asia/Jerusalem"
    )


def in_israel_email_window(now: datetime | None = None) -> bool:
    ok, _ = israel_email_window_status(now)
    return ok
