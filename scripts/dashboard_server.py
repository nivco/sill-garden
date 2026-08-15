#!/usr/bin/env python3
"""Local Sill Garden analytics dashboard — http://127.0.0.1:8793/dashboard"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_HTML = ROOT / "dashboard" / "index.html"
LATEST_JSON = ROOT / "products" / "analytics" / "latest.json"
PORT = 8793
NO_CACHE = ("Cache-Control", "no-store, no-cache, must-revalidate")

_refresh_lock = False


def port_in_use(host: str, port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform == "win32":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((host, port))
        return False
    except OSError:
        return True
    finally:
        probe.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header(*NO_CACHE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in ("/", "/dashboard"):
            if not DASHBOARD_HTML.is_file():
                self._send(404, b"dashboard missing", "text/plain")
                return
            self._send(200, DASHBOARD_HTML.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/scorecard":
            if not LATEST_JSON.is_file():
                payload = {
                    "ok": False,
                    "error": "No scorecard yet — click Refresh",
                    "hero": {},
                    "setup": {"checks": []},
                    "insights": ["Run refresh to generate products/analytics/latest.json"],
                }
                raw = json.dumps(payload).encode("utf-8")
                self._send(200, raw, "application/json")
                return
            self._send(200, LATEST_JSON.read_bytes(), "application/json")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        global _refresh_lock
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/api/refresh":
            self._send(404, b"not found", "text/plain")
            return
        if _refresh_lock:
            self._send(409, json.dumps({"ok": False, "error": "refresh in progress"}).encode(), "application/json")
            return
        _refresh_lock = True
        try:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "analytics_summary.py")],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            opt_out = ""
            opt_err = ""
            if proc.returncode == 0:
                opt = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "traffic_optimizer.py")],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
                opt_out = (opt.stdout or "")[-1000:]
                opt_err = (opt.stderr or "")[-1000:]
                # Re-run scorecard so action queue is attached after optimizer writes it.
                if opt.returncode == 0:
                    proc2 = subprocess.run(
                        [sys.executable, str(ROOT / "scripts" / "analytics_summary.py")],
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                        timeout=180,
                        check=False,
                    )
                    if proc2.returncode == 0:
                        proc = proc2
            ok = proc.returncode == 0 and LATEST_JSON.is_file()
            data = {}
            if LATEST_JSON.is_file():
                data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
            payload = {
                "ok": ok,
                "returncode": proc.returncode,
                "stdout": ((proc.stdout or "") + ("\n" + opt_out if opt_out else ""))[-2000:],
                "stderr": ((proc.stderr or "") + ("\n" + opt_err if opt_err else ""))[-2000:],
                "scorecard": data,
            }
            self._send(200 if ok else 500, json.dumps(payload).encode("utf-8"), "application/json")
        finally:
            _refresh_lock = False


def main() -> int:
    host = "127.0.0.1"
    if port_in_use(host, PORT):
        print(f"Port {PORT} in use — stop the other dashboard_server.py first")
        return 1
    if not DASHBOARD_HTML.is_file():
        print(f"Missing {DASHBOARD_HTML}")
        return 1
    print(f"Sill Garden dashboard -> http://{host}:{PORT}/dashboard")
    print("Refresh runs analytics_summary.py + traffic_optimizer.py (reads .env)")
    HTTPServer((host, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
