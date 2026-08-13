#!/usr/bin/env python3
"""Fail automations when GA4/GSC measurement is broken.

  python scripts/measurement_gate.py --strict
  python scripts/measurement_gate.py --warn-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "products" / "analytics" / "latest.json"
STATUS = ROOT / "products" / "analytics" / "google-access-status.json"


def _latest_google_errors() -> tuple[str | None, str | None]:
    if not LATEST.is_file():
        return "missing latest.json", "missing latest.json"
    try:
        data = json.loads(LATEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "unreadable latest.json", "unreadable latest.json"
    sources = data.get("sources") or {}
    ga4_err = (sources.get("ga4") or {}).get("error")
    gsc_err = (sources.get("gsc") or {}).get("error")
    return (
        str(ga4_err)[:240] if ga4_err else None,
        str(gsc_err)[:240] if gsc_err else None,
    )


def google_access_ready(*, refresh: bool = False) -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    from analytics_summary import load_dotenv

    load_dotenv()
    status: dict = {"ready": False, "ga4": None, "gsc": None, "source": None}

    if refresh or not STATUS.is_file():
        from check_google_access import main as probe_main

        probe_main()
    if STATUS.is_file():
        try:
            file_status = json.loads(STATUS.read_text(encoding="utf-8"))
            status.update(
                {
                    "ready": bool(file_status.get("ready")),
                    "ga4": file_status.get("ga4_data_api"),
                    "gsc": file_status.get("gsc_api"),
                    "source": "google-access-status.json",
                    "checked": file_status.get("checked"),
                    "next_steps": file_status.get("next_steps") or [],
                }
            )
        except (json.JSONDecodeError, OSError):
            pass

    ga4_err, gsc_err = _latest_google_errors()
    if ga4_err or gsc_err:
        status["ready"] = False
        status["latest_ga4_error"] = ga4_err
        status["latest_gsc_error"] = gsc_err
    elif status.get("ga4") == "ok" and status.get("gsc") == "ok":
        status["ready"] = True

    if not status["ready"] and not status.get("next_steps"):
        status["next_steps"] = [
            "Run MTS: python scripts/google_oauth_login.py --force",
            "Then: python scripts/google_token_sync.py",
        ]
    return status


def require_google_access(*, strict: bool = True, warn_only: bool = False) -> int:
    status = google_access_ready(refresh=False)
    print(json.dumps(status, indent=2))
    if status.get("ready"):
        print("Measurement gate: GA4 + GSC OK")
        return 0
    msg = "Measurement gate FAILED — GA4/GSC not ready; automations would run blind."
    if warn_only:
        print(f"WARNING: {msg}", file=sys.stderr)
        return 0
    print(msg, file=sys.stderr)
    for step in status.get("next_steps") or []:
        print(f"  → {step}", file=sys.stderr)
    return 1 if strict else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Block automations when Google analytics APIs are down")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when not ready")
    parser.add_argument("--warn-only", action="store_true", help="Print warning but exit 0")
    parser.add_argument("--refresh", action="store_true", help="Re-probe Google access first")
    args = parser.parse_args()
    if args.refresh:
        google_access_ready(refresh=True)
    return require_google_access(strict=args.strict, warn_only=args.warn_only)


if __name__ == "__main__":
    raise SystemExit(main())
