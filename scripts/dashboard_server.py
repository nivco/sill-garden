#!/usr/bin/env python3
"""Local Sill Garden analytics dashboard — http://127.0.0.1:8793/dashboard"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_HTML = ROOT / "dashboard" / "index.html"
LATEST_JSON = ROOT / "products" / "analytics" / "latest.json"
ACTION_QUEUE = ROOT / "products" / "traffic" / "action-queue.json"
GROWTH_STATE = ROOT / "products" / "growth" / "daily-agent-state.json"
GROWTH_DIST = ROOT / "products" / "growth" / "distribution" / "latest.json"
AI_CITATION = ROOT / "products" / "growth" / "ai-citation" / "latest.json"
LEARNING = ROOT / "products" / "analytics" / "learning-snapshot.json"
BOARD_QUEUE = ROOT / "reports" / "board" / "action-queue.json"
PORT = 8793
NO_CACHE = ("Cache-Control", "no-store, no-cache, must-revalidate")
SERVER_TAG = "v2-live-refresh"

_refresh_lock = False


def read_json(path: Path) -> dict:
    """Read JSON, retrying briefly: a script may still be writing the file."""
    if not path.is_file():
        return {}
    last_err: Exception | None = None
    for _ in range(3):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - keep the dashboard up
            last_err = exc
            time.sleep(0.05)
    print(f"warning: failed to read {path.name}: {last_err}", file=sys.stderr)
    return {}


def run_script(name: str, timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def scorecard_payload(source: str) -> dict:
    data = read_json(LATEST_JSON)
    queue = read_json(ACTION_QUEUE)
    if queue.get("actions"):
        data["actions"] = queue["actions"][:12]
    data["traffic"] = queue
    growth_state = read_json(GROWTH_STATE)
    dist = read_json(GROWTH_DIST)
    ai = read_json(AI_CITATION)
    learning = read_json(LEARNING)
    board = read_json(BOARD_QUEUE)
    data["growth"] = {
        "state": growth_state,
        "distribution": dist,
        "ai_citation": {
            "visibility_score": ai.get("visibility_score"),
            "mentions": ai.get("mentions"),
            "prompts": ai.get("prompts"),
            "generated_at": ai.get("generated_at"),
        }
        if ai
        else {},
        "learnings": (learning.get("learnings") or [])[:8],
        "board_open": len(
            [
                i
                for i in (board.get("items") or [])
                if not i.get("done") and (i.get("role") or "") != "ai-visibility"
            ]
        ),
    }
    data["_source"] = source
    data["_server"] = SERVER_TAG
    if LATEST_JSON.is_file():
        data["_age_sec"] = int(time.time() - LATEST_JSON.stat().st_mtime)
    return data


def run_live() -> tuple[dict, dict]:
    """Pull GA4/GSC fresh, then re-run the optimizer so actions match the new data."""
    proc = run_script("analytics_summary.py")
    opt_out = ""
    opt_err = ""
    if proc.returncode == 0:
        opt = run_script("traffic_optimizer.py")
        opt_out = (opt.stdout or "")[-1000:]
        opt_err = (opt.stderr or "")[-1000:]
    ok = proc.returncode == 0 and LATEST_JSON.is_file()
    meta = {
        "ok": ok,
        "returncode": proc.returncode,
        "stdout": ((proc.stdout or "") + ("\n" + opt_out if opt_out else ""))[-2000:],
        "stderr": ((proc.stderr or "") + ("\n" + opt_err if opt_err else ""))[-2000:],
    }
    return scorecard_payload("live" if ok else "live-failed"), meta


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

    def _send_json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json")

    def _refresh(self, wrapped: bool) -> None:
        global _refresh_lock
        if _refresh_lock:
            self._send_json(409, {"ok": False, "busy": True, "error": "refresh already in progress"})
            return
        _refresh_lock = True
        try:
            data, meta = run_live()
        finally:
            _refresh_lock = False
        code = 200 if meta["ok"] else 500
        if wrapped:
            meta["scorecard"] = data
            self._send_json(code, meta)
            return
        if not meta["ok"]:
            data["error"] = (meta["stderr"] or meta["stdout"] or "refresh failed").strip()[-800:]
        self._send_json(code, data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if path in ("/", "/dashboard"):
            if not DASHBOARD_HTML.is_file():
                self._send(404, b"dashboard missing", "text/plain")
                return
            self._send(200, DASHBOARD_HTML.read_bytes(), "text/html; charset=utf-8")
            return
        if path in ("/api/scorecard", "/api/refresh"):
            cached = query.get("cached", ["0"])[0] in ("1", "true")
            if not cached:
                self._refresh(wrapped=False)
                return
            if not LATEST_JSON.is_file():
                self._send_json(
                    200,
                    {
                        "ok": False,
                        "error": "No scorecard yet — click Refresh",
                        "hero": {},
                        "setup": {"checks": []},
                        "insights": ["Run refresh to generate products/analytics/latest.json"],
                        "_source": "empty",
                    },
                )
                return
            self._send_json(200, scorecard_payload("cache"))
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/api/refresh":
            self._send(404, b"not found", "text/plain")
            return
        self._refresh(wrapped=True)


def main() -> int:
    host = "127.0.0.1"
    if port_in_use(host, PORT):
        print(f"Port {PORT} in use — stop the other dashboard_server.py first")
        return 1
    if not DASHBOARD_HTML.is_file():
        print(f"Missing {DASHBOARD_HTML}")
        return 1
    print(f"Sill Garden dashboard -> http://{host}:{PORT}/dashboard")
    print("Live fetch = analytics_summary.py + traffic_optimizer.py (reads .env)")
    print("GET /api/scorecard = live · GET /api/scorecard?cached=1 = last snapshot")
    HTTPServer((host, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
