#!/usr/bin/env python3
"""Send Sill Garden growth emails (Resend / SMTP / Buttondown) with MTS-style guards."""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_dotenv
from email_quiet_hours import israel_email_window_status
from email_send_guard import is_force_send, record_email_send, should_send_email

ROOT = Path(__file__).resolve().parents[1]
BUTTONDOWN_API = "https://api.buttondown.com/v1"


def _sibling_env(keys: list[str]) -> None:
    wanted = {k for k in keys if not (os.environ.get(k) or "").strip()}
    if not wanted:
        return
    for path in (
        Path(r"E:/Projects/makertoolstack/.env"),
        Path(r"E:/Projects/invoice-chase/.env"),
        Path(r"E:/Projects/ai-visibility/.env"),
    ):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in wanted and value.strip():
                os.environ.setdefault(key, value.strip().strip('"').strip("'"))
                wanted.discard(key)
        if not wanted:
            return


def _buttondown_request(method: str, path: str, token: str, payload: dict | None = None, extra_headers: dict | None = None) -> dict:
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"{BUTTONDOWN_API}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def send_via_buttondown(subject: str, body: str, *, live: bool) -> str:
    token = (os.environ.get("BUTTONDOWN_API_KEY") or "").strip()
    if not token:
        raise RuntimeError("Missing BUTTONDOWN_API_KEY")
    target_email = (os.environ.get("GROWTH_REPORT_EMAIL") or "").strip().lower()
    subs = _buttondown_request("GET", "/subscribers?limit=50", token).get("results") or []
    if not subs:
        raise RuntimeError("No Buttondown subscribers")
    sub = next((s for s in subs if (s.get("email_address") or "").lower() == target_email), subs[0])
    draft = _buttondown_request(
        "POST",
        "/emails",
        token,
        {"subject": subject, "body": body, "status": "draft"},
    )
    email_id = draft["id"]
    headers = {"X-Buttondown-Test-Mode": "true"} if not live else None
    _buttondown_request(
        "POST",
        f"/emails/{email_id}/send-draft",
        token,
        {"subscribers": [sub["id"]]},
        extra_headers=headers,
    )
    return f"buttondown:{email_id} -> {sub.get('email_address')}"


def send_via_smtp(subject: str, body: str) -> str:
    host = (os.environ.get("GROWTH_SMTP_HOST") or "").strip()
    user = (os.environ.get("GROWTH_SMTP_USER") or "").strip()
    password = (
        (os.environ.get("GROWTH_SMTP_PASS") or "").strip()
        or (os.environ.get("GROWTH_SMTP_PASSWORD") or "").strip()
    )
    to_addr = (os.environ.get("GROWTH_REPORT_EMAIL") or "").strip()
    port = int(os.environ.get("GROWTH_SMTP_PORT") or "587")
    if not all([host, user, password, to_addr]):
        raise RuntimeError("SMTP not configured")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain", "utf-8"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=60) as server:
        server.starttls(context=ctx)
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
    return f"smtp -> {to_addr}"


def send_via_resend(subject: str, body: str) -> str:
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    email_from = (os.environ.get("EMAIL_FROM") or "").strip()
    to_addr = (os.environ.get("GROWTH_REPORT_EMAIL") or "").strip()
    if not (key and email_from and to_addr):
        raise RuntimeError("Resend not configured")
    payload = {"from": email_from, "to": [to_addr], "subject": subject, "text": body}
    try:
        import httpx

        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Resend HTTP {resp.status_code}: {resp.text[:200]}")
        return f"resend -> {to_addr}"
    except ImportError:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=data,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "sill-garden-notify/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
        return f"resend -> {to_addr}"


def send_growth_report(
    subject: str,
    body: str,
    *,
    dry_run: bool = False,
    channel: str = "sill-growth",
    force: bool = False,
) -> dict:
    load_dotenv()
    _sibling_env(
        [
            "GROWTH_REPORT_EMAIL",
            "GROWTH_SMTP_HOST",
            "GROWTH_SMTP_USER",
            "GROWTH_SMTP_PASS",
            "GROWTH_SMTP_PASSWORD",
            "GROWTH_SMTP_PORT",
            "BUTTONDOWN_API_KEY",
            "RESEND_API_KEY",
            "EMAIL_FROM",
        ]
    )
    if dry_run:
        return {"skipped": True, "subject": subject, "preview": body[:500]}

    force = force or is_force_send()
    allowed, guard_reason = should_send_email(channel, subject, body, force=force)
    if not allowed:
        return {"ok": False, "skipped": True, "detail": guard_reason}

    allowed, reason = israel_email_window_status()
    if not allowed and not force:
        return {"ok": False, "skipped": True, "detail": reason}

    live = os.environ.get("AUTOMATION_LIVE", "").strip().lower() in ("1", "true", "yes")
    errors: list[str] = []
    to_addr = (os.environ.get("GROWTH_REPORT_EMAIL") or "").strip()

    if (os.environ.get("BUTTONDOWN_API_KEY") or "").strip():
        try:
            detail = send_via_buttondown(subject, body, live=live)
            record_email_send(channel, subject, body, recipient=to_addr, via="buttondown")
            return {"ok": True, "via": "buttondown", "detail": detail}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"buttondown: {exc}")

    if (os.environ.get("RESEND_API_KEY") or "").strip():
        try:
            detail = send_via_resend(subject, body)
            record_email_send(channel, subject, body, recipient=to_addr, via="resend")
            return {"ok": True, "via": "resend", "detail": detail}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"resend: {exc}")

    if (os.environ.get("GROWTH_SMTP_HOST") or "").strip():
        try:
            detail = send_via_smtp(subject, body)
            record_email_send(channel, subject, body, recipient=to_addr, via="smtp")
            return {"ok": True, "via": "smtp", "detail": detail}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"smtp: {exc}")

    return {
        "ok": False,
        "skipped": False,
        "detail": "; ".join(errors) or "no email transport configured",
    }
