"""
Task store — one-off and recurring tasks backing the scheduler tool, the
heartbeat loop, and standing orders. Plain JSON on disk so the state is
inspectable and survives restarts.
"""

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from remy.config import DATA_DIR

TASKS_FILE = DATA_DIR / "tasks.json"

_lock = threading.Lock()


def _load() -> dict[str, dict[str, Any]]:
    if TASKS_FILE.exists():
        try:
            return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save(data: dict[str, dict[str, Any]]) -> None:
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TASKS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def add_task(description: str, due_at: str | None = None,
             recur_minutes: int | None = None, created_by: str = "user") -> dict:
    task_id = uuid.uuid4().hex[:10]
    task = {
        "id": task_id,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "due_at": due_at,
        "recur_minutes": recur_minutes,
        "created_by": created_by,
        "status": "pending",     # pending | done | cancelled
        "last_run_at": None,
    }
    with _lock:
        data = _load()
        data[task_id] = task
        _save(data)
    return task


def list_tasks(include_closed: bool = False) -> list[dict]:
    with _lock:
        data = _load()
    tasks = list(data.values())
    if not include_closed:
        tasks = [t for t in tasks if t["status"] == "pending"]
    return sorted(tasks, key=lambda t: t.get("due_at") or t["created_at"])


def set_status(task_id: str, status: str) -> bool:
    with _lock:
        data = _load()
        if task_id not in data:
            return False
        data[task_id]["status"] = status
        _save(data)
    return True


def mark_ran(task_id: str) -> None:
    """Record a run; recompute due time for recurring tasks, close one-offs."""
    now = datetime.now(timezone.utc)
    with _lock:
        data = _load()
        task = data.get(task_id)
        if not task:
            return
        task["last_run_at"] = now.isoformat()
        if task.get("recur_minutes"):
            task["due_at"] = (now + timedelta(minutes=task["recur_minutes"])).isoformat()
        else:
            task["status"] = "done"
        _save(data)


def due_tasks(now: datetime | None = None) -> list[dict]:
    """Pending tasks whose due time has arrived (or that have no due time)."""
    now = now or datetime.now(timezone.utc)
    due = []
    for t in list_tasks():
        if not t["due_at"]:
            due.append(t)
            continue
        try:
            due_at = datetime.fromisoformat(t["due_at"])
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=timezone.utc)
            if due_at <= now:
                due.append(t)
        except ValueError:
            due.append(t)  # unparseable due date → surface it rather than hide it
    return due


def overdue_tasks(hours: int = 24) -> list[dict]:
    """Pending tasks past due by more than `hours` (standing order trigger)."""
    now = datetime.now(timezone.utc)
    out = []
    for t in list_tasks():
        if not t["due_at"]:
            continue
        try:
            due_at = datetime.fromisoformat(t["due_at"])
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=timezone.utc)
            if now - due_at > timedelta(hours=hours):
                out.append(t)
        except ValueError:
            continue
    return out
