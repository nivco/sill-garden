#!/usr/bin/env python3
"""Probe GA4/GSC access for Sill Garden. Writes products/analytics/google-access-status.json."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytics_summary import fetch_ga4, fetch_gsc, load_dotenv

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "products" / "analytics" / "google-access-status.json"


def main() -> int:
    load_dotenv()
    ga4_pid = (os.environ.get("GA4_PROPERTY_ID") or "").strip()
    gsc_site = (os.environ.get("GSC_SITE_URL") or "sc-domain:sillgarden.com").strip()
    status: dict = {
        "checked": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "ga4_property_id": ga4_pid,
        "gsc_site_url": gsc_site,
        "auth_mode": (os.environ.get("GOOGLE_AUTH") or "sa").strip().lower(),
        "ga4_data_api": None,
        "gsc_api": None,
        "ready": False,
        "next_steps": [],
    }

    if ga4_pid:
        try:
            fetch_ga4(ga4_pid)
            status["ga4_data_api"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["ga4_data_api"] = str(exc)[:240]
            status["next_steps"].append("Fix GA4: grant OAuth/SA Viewer on property 549929269")
    else:
        status["ga4_data_api"] = "missing GA4_PROPERTY_ID"
        status["next_steps"].append("Set GA4_PROPERTY_ID")

    if gsc_site:
        try:
            fetch_gsc(gsc_site)
            status["gsc_api"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["gsc_api"] = str(exc)[:240]
            status["next_steps"].append(
                "Fix GSC: ensure OAuth has webmasters.readonly and access to sc-domain:sillgarden.com"
            )
    else:
        status["gsc_api"] = "missing GSC_SITE_URL"
        status["next_steps"].append("Set GSC_SITE_URL=sc-domain:sillgarden.com")

    status["ready"] = status["ga4_data_api"] == "ok" and status["gsc_api"] == "ok"
    if not status["ready"] and not status["next_steps"]:
        status["next_steps"] = [
            "cd E:\\Projects\\makertoolstack && python scripts\\google_oauth_login.py --force",
            "python scripts\\google_token_sync.py  # include nivco/sill-garden",
        ]

    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0 if status["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
