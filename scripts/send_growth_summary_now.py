#!/usr/bin/env python3
"""Build and send the unified Sill Garden growth summary email now (MTS parity).

  python scripts/send_growth_summary_now.py --dry-run
  python scripts/send_growth_summary_now.py --refresh --force
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from automation_common import load_dotenv
from growth_report_builder import build_unified_growth_email
from growth_report_email import send_growth_report


def main() -> int:
    load_dotenv()
    dry = "--dry-run" in sys.argv
    if "--refresh" in sys.argv:
        print("Refreshing analytics_summary.py...")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "analytics_summary.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(proc.stderr or proc.stdout, file=sys.stderr)
            return proc.returncode
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "traffic_optimizer.py")],
            cwd=str(ROOT),
            check=False,
        )
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "outcome_health.py"), "--warn-only"],
            cwd=str(ROOT),
            check=False,
        )

    report = build_unified_growth_email(header_title="Sill Garden Traffic & Growth Summary")
    out = ROOT / "products" / "growth" / "daily-reports" / f"{report['date']}-summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if dry:
        print(report["email_subject"])
        print("-" * 44)
        sys.stdout.buffer.write((report["email_body"] + "\n").encode("utf-8", errors="replace"))
        print("-" * 44)
        print(f"Saved: {out}")
        return 0

    force = "--force" in sys.argv
    if force:
        os.environ["GROWTH_EMAIL_FORCE"] = "1"
    result = send_growth_report(
        report["email_subject"],
        report["email_body"],
        dry_run=False,
        force=force,
        channel="sill-growth",
    )
    print(json.dumps(result, indent=2))
    print(f"Saved: {out}")
    return 0 if result.get("ok") or result.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
