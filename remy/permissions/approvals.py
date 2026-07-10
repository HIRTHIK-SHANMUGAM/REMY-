"""
Approval queue — high-risk actions block here until the user decides.

Requests persist to remy_data/approvals.json so they survive restarts and can
be surfaced by the dashboard, a desktop notification, or the chat UI. A tool
call in the REQUIRES_APPROVAL tier waits (with timeout) for a verdict; on
timeout it is treated as denied — REMY never proceeds on its own.
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from remy.config import DATA_DIR

APPROVALS_FILE = DATA_DIR / "approvals.json"
DEFAULT_TIMEOUT_S = 300  # 5 minutes, then auto-deny

_lock = threading.Lock()
_events: dict[str, threading.Event] = {}


def _load() -> dict[str, dict[str, Any]]:
    if APPROVALS_FILE.exists():
        try:
            return json.loads(APPROVALS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save(data: dict[str, dict[str, Any]]) -> None:
    APPROVALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def create_request(tool: str, args: dict[str, Any], reason: str, actor: str) -> str:
    req_id = uuid.uuid4().hex[:12]
    with _lock:
        data = _load()
        data[req_id] = {
            "id": req_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "tool": tool,
            "args": {k: str(v)[:300] for k, v in args.items()},
            "reason": reason,
            "status": "pending",   # pending | approved | denied | expired
        }
        _save(data)
        _events[req_id] = threading.Event()
    _notify_user(data[req_id])
    return req_id


def _notify_user(req: dict[str, Any]) -> None:
    """Best-effort desktop notification; the dashboard polls regardless."""
    try:
        import platform, subprocess
        msg = f"REMY needs approval: {req['tool']} — {req['reason'][:120]}"
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(
                ["osascript", "-e",
                 f'display notification "{msg}" with title "REMY"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Linux":
            subprocess.Popen(["notify-send", "REMY", msg],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Windows":
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command",
                 f"msg * /TIME:10 \"{msg}\""],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # notification is best-effort; approval still shows in the UI


def resolve(req_id: str, approve: bool) -> bool:
    """Called by the API/dashboard when the user clicks approve/deny."""
    with _lock:
        data = _load()
        req = data.get(req_id)
        if not req or req["status"] != "pending":
            return False
        req["status"] = "approved" if approve else "denied"
        req["resolved_ts"] = datetime.now(timezone.utc).isoformat()
        _save(data)
        ev = _events.get(req_id)
    if ev:
        ev.set()
    return True


def wait_for_verdict(req_id: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> str:
    """
    Block until the user decides, or expire (= denied) after timeout.

    Polls the approvals file as well as the in-process event: the verdict may
    be written by a different process (the dashboard API) than the one whose
    tool call is blocked here (e.g. the MCP server serving the voice agent).
    """
    import time
    deadline = time.monotonic() + timeout_s
    ev = _events.get(req_id)
    while time.monotonic() < deadline:
        if ev is not None and ev.wait(2.0):
            break
        if ev is None:
            time.sleep(2.0)
        with _lock:
            status = _load().get(req_id, {}).get("status", "denied")
        if status != "pending":
            return status
    with _lock:
        data = _load()
        req = data.get(req_id)
        if not req:
            return "denied"
        if req["status"] == "pending":
            req["status"] = "expired"
            _save(data)
            return "expired"
        return req["status"]


def pending_requests() -> list[dict[str, Any]]:
    with _lock:
        data = _load()
    return sorted(
        (r for r in data.values() if r["status"] == "pending"),
        key=lambda r: r["ts"], reverse=True,
    )
