#!/usr/bin/env python3
"""Send ops/growth emails via SMTP or Resend.

Prefers GROWTH_SMTP_* (GitHub Actions). Falls back to RESEND_API_KEY + EMAIL_FROM
so local catch-up runs can still notify when SMTP secrets are missing from the repo.
"""

from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

from automation_common import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def _load_sibling_env_keys(keys: list[str]) -> None:
    """Pull missing mail keys from sibling project .env files (local only)."""
    siblings = [
        Path(r"E:/Projects/invoice-chase/.env"),
        Path(r"E:/Projects/ai-visibility/.env"),
        Path(r"E:/Projects/makertoolstack/.env"),
    ]
    wanted = {k for k in keys if not (os.environ.get(k) or "").strip()}
    if not wanted:
        return
    for path in siblings:
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


def report_to() -> str:
    return (os.environ.get("GROWTH_REPORT_EMAIL") or "nivooo@gmail.com").strip()


def send_email(*, subject: str, body: str, to_addr: str | None = None) -> dict:
    """Send plaintext email. Returns {ok, via, detail}."""
    load_dotenv()
    _load_sibling_env_keys(
        [
            "GROWTH_REPORT_EMAIL",
            "GROWTH_SMTP_HOST",
            "GROWTH_SMTP_USER",
            "GROWTH_SMTP_PASS",
            "GROWTH_SMTP_PASSWORD",
            "GROWTH_SMTP_PORT",
            "RESEND_API_KEY",
            "EMAIL_FROM",
        ]
    )
    to_addr = (to_addr or report_to()).strip()
    if not to_addr:
        return {"ok": False, "via": "none", "detail": "no recipient"}

    host = (os.environ.get("GROWTH_SMTP_HOST") or "").strip()
    user = (os.environ.get("GROWTH_SMTP_USER") or "").strip()
    password = (
        (os.environ.get("GROWTH_SMTP_PASS") or "").strip()
        or (os.environ.get("GROWTH_SMTP_PASSWORD") or "").strip()
    )
    port = int(os.environ.get("GROWTH_SMTP_PORT") or "587")
    if host and user and password:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to_addr
        msg.set_content(body)
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return {"ok": True, "via": "smtp", "detail": f"sent to {to_addr}"}

    resend_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    email_from = (os.environ.get("EMAIL_FROM") or "").strip()
    if resend_key and email_from:
        payload_obj = {
            "from": email_from,
            "to": [to_addr],
            "subject": subject,
            "text": body,
        }
        try:
            import httpx

            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json=payload_obj,
                timeout=30.0,
            )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "via": "resend",
                    "detail": f"HTTP {resp.status_code}: {resp.text[:300]}",
                }
            return {
                "ok": True,
                "via": "resend",
                "detail": f"sent to {to_addr}; {resp.text[:120]}",
            }
        except ImportError:
            payload = json.dumps(payload_obj).encode("utf-8")
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "sill-garden-notify/1.0",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                return {"ok": True, "via": "resend", "detail": f"sent to {to_addr}; {raw[:120]}"}
            except urllib.error.HTTPError as exc:
                err = exc.read().decode("utf-8", errors="replace")[:300]
                return {"ok": False, "via": "resend", "detail": f"HTTP {exc.code}: {err}"}

    return {
        "ok": False,
        "via": "none",
        "detail": "missing GROWTH_SMTP_* and RESEND_API_KEY/EMAIL_FROM",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body-file", type=Path, required=True)
    args = parser.parse_args()
    result = send_email(subject=args.subject, body=args.body_file.read_text(encoding="utf-8"))
    print(result)
    raise SystemExit(0 if result.get("ok") else 1)
