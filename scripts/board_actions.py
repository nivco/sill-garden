#!/usr/bin/env python3
"""Board / growth action queue for Sill Garden."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from automation_common import load_json, now_utc, save_json

ROOT = Path(__file__).resolve().parents[1]
BOARD_DIR = ROOT / "reports" / "board"
QUEUE_PATH = BOARD_DIR / "action-queue.json"
TRAFFIC_QUEUE = ROOT / "products" / "traffic" / "action-queue.json"


def load_queue() -> dict:
    data = load_json(QUEUE_PATH, None)
    if isinstance(data, dict):
        data.setdefault("version", 1)
        data.setdefault("items", [])
        return data
    return {"version": 1, "items": []}


def save_queue(queue: dict) -> None:
    queue["updated"] = now_utc()
    save_json(QUEUE_PATH, queue)


def _fingerprint(role: str, action_type: str, target: str) -> str:
    raw = f"{role}|{action_type}|{target}".lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def enqueue(
    *,
    role: str,
    action_type: str,
    title: str,
    detail: str,
    target: str = "",
    auto: bool = False,
    priority: str = "P2",
) -> dict | None:
    queue = load_queue()
    fp = _fingerprint(role, action_type, target or title)
    for item in queue["items"]:
        if item.get("fingerprint") == fp and not item.get("done"):
            return None
    item = {
        "id": fp,
        "fingerprint": fp,
        "role": role,
        "type": action_type,
        "title": title,
        "detail": detail,
        "target": target,
        "auto": auto,
        "priority": priority,
        "done": False,
        "created": now_utc(),
    }
    queue["items"].append(item)
    save_queue(queue)
    return item


def dedupe_proposed(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        key = f"{item.get('type')}:{item.get('slug') or item.get('target') or item.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def sync_manual_to_traffic_queue(board: dict | None = None) -> None:
    board = board or load_queue()
    traffic = load_json(TRAFFIC_QUEUE, {}) or {}
    actions = list(traffic.get("actions") or [])
    existing = {(a.get("title") or "") for a in actions}
    skip_substrings = (
        "steady",
        "healthy",
        "maintain cadence",
        "extend kpi",
        "spot-check core web vitals",
        "keep astro build green",
    )
    for item in board.get("items") or []:
        if item.get("done") or item.get("auto"):
            continue
        # AI citation demo misses are noise on the main Do-next list.
        if (item.get("role") or "") == "ai-visibility":
            continue
        title = item.get("title") or item.get("type")
        if not title or title in existing:
            continue
        low = title.lower()
        if any(s in low for s in skip_substrings):
            continue
        # Board "status OK" fluff should not flood Do-next.
        if (item.get("type") or "") == "board" and (item.get("priority") or "P2") == "P2":
            if low.startswith("[") or "from weekly" in (item.get("detail") or "").lower():
                continue
        actions.append(
            {
                "priority": item.get("priority") or "P2",
                "category": item.get("role") or "growth",
                "title": title,
                "detail": item.get("detail") or "",
                "auto": False,
                "done": False,
                "created": item.get("created") or now_utc(),
            }
        )
        existing.add(title)
    traffic["actions"] = actions[:12]
    traffic["generated_at"] = now_utc()
    save_json(TRAFFIC_QUEUE, traffic)


def record_applied(queue: dict, change: dict) -> None:
    queue.setdefault("applied_log", []).append(
        {
            "at": now_utc(),
            "type": change.get("type"),
            "slug": change.get("slug"),
            "reason": change.get("reason"),
        }
    )
    save_queue(queue)


def pick_auto_changes(proposed: list[dict], *, max_items: int = 3) -> list[dict]:
    """Only auto-apply safe SEO patches that are explicitly marked auto_safe."""
    safe = [
        p
        for p in proposed
        if p.get("type") == "tune_guide_seo" and p.get("slug") and p.get("auto_safe")
    ]
    return safe[:max_items]


def format_impact_lines(items: list[dict]) -> list[str]:
    lines = []
    for item in items:
        lines.append(
            f"{item.get('type')}:{item.get('slug') or item.get('target')} — {item.get('reason') or item.get('detail')}"
        )
    return lines


def measure_impacts(
    queue: dict | None = None,
    metrics: dict | None = None,
    today: str | None = None,
) -> list[dict[str, Any]]:
    """Placeholder for 7-day impact measurement; kept for API parity with MTS."""
    return []


def _metrics_slice(snapshot: dict) -> dict:
    """Extract flat metric slice from snapshot for queue scoring."""
    return {k: v for k, v in snapshot.items() if isinstance(v, (int, float, str))}


def build_queue_items(
    snapshot: dict, role_outputs: dict, cadence: str
) -> list[dict]:
    """Turn exec-board role outputs into queue items."""
    skip_substrings = (
        "steady",
        "healthy",
        "maintain cadence",
        "extend kpi",
        "spot-check core web vitals",
        "keep astro build green",
        "no threshold breaches",
    )
    items: list[dict] = []
    for rid, out in role_outputs.items():
        for action in out.get("actions", [])[:2]:
            low = action.lower()
            if any(s in low for s in skip_substrings):
                continue
            fp = _fingerprint(rid, "board", action[:60])
            items.append(
                {
                    "id": fp,
                    "fingerprint": fp,
                    "role": rid,
                    "type": "board",
                    "title": action[:120],
                    "detail": f"From {cadence} board run",
                    "target": "",
                    "auto": False,
                    "priority": "P1" if rid == "ceo" else "P2",
                    "done": False,
                    "created": now_utc(),
                }
            )
    return items


def merge_queue(queue: dict, new_items: list[dict]) -> int:
    """Merge new items into queue, deduplicating by fingerprint. Returns count added."""
    existing_fps = {i.get("fingerprint") for i in queue.get("items", []) if not i.get("done")}
    added = 0
    for item in new_items:
        if item.get("fingerprint") in existing_fps:
            continue
        queue.setdefault("items", []).append(item)
        existing_fps.add(item["fingerprint"])
        added += 1
    return added


def format_queue_section(queue: dict) -> str:
    """Render the action queue as a markdown section for the board report."""
    items = queue.get("items") or []
    open_items = [i for i in items if not i.get("done")]
    if not open_items:
        return "## Action queue\n\nNo open items."
    lines = ["## Action queue", ""]
    for item in open_items[:15]:
        role = item.get("role") or "?"
        pri = item.get("priority") or "P2"
        title = item.get("title") or item.get("type") or "untitled"
        lines.append(f"- [{pri}] **{role}**: {title}")
    done_count = len(items) - len(open_items)
    if done_count:
        lines.append(f"\n_{done_count} completed items hidden._")
    return "\n".join(lines)
