"""
Heartbeat — REMY's autonomy loop.

On a configurable interval (REMY_HEARTBEAT_MINUTES) REMY wakes with no user
input, gathers state, lets the Watcher decide, and acts through the same
permission-gated tool layer as everything else. Every cycle writes audit
entries (actor=heartbeat) — including the "nothing to do" cycles — and a
status snapshot for the dashboard. Runs as a background scheduler inside the
API process, independent of any open chat window.
"""

import json
import logging
import threading
from datetime import datetime, timezone

from remy import tasks
from remy.agents import watcher
from remy.config import DATA_DIR, config
from remy.permissions import audit
from remy.permissions.approvals import _notify_user as desktop_notify

logger = logging.getLogger("remy-heartbeat")

STATUS_FILE = DATA_DIR / "heartbeat.json"

_carry_state: dict = {}
_scheduler = None
_lock = threading.Lock()


def _apply_action(action: dict) -> str:
    kind = action.get("kind", "log_only")

    if kind == "notify_user":
        message = action.get("message", "")
        desktop_notify({"tool": "heartbeat", "reason": message})
        audit.log_event("notify_user", {"message": message}, "auto",
                        "auto-approved", outcome="notification sent",
                        actor="heartbeat")
        return f"notified: {message}"

    if kind == "execute":
        instruction = action.get("instruction", "")
        # Sanity-check autonomous work before running it (advisory layer on
        # top of the code-enforced permission gate).
        from remy.agents import reviewer
        approved, note = reviewer.review_action(instruction,
                                                "autonomous heartbeat action")
        if not approved:
            audit.log_event("heartbeat_execute", {"instruction": instruction},
                            "approval", "blocked", outcome=f"reviewer: {note}",
                            actor="heartbeat")
            return f"execute rejected by reviewer: {note}"
        from remy.agents import executor
        try:
            report = executor.run_task(instruction, actor="heartbeat")
        except Exception as exc:  # LLMUnavailable or tool loop failure
            report = f"executor failed: {exc}"
        audit.log_event("heartbeat_execute", {"instruction": instruction},
                        "logged", "logged", outcome=report[:500],
                        actor="heartbeat")
        return f"executed: {report[:200]}"

    note = action.get("note", "nothing to do")
    audit.log_event("heartbeat_check", {}, "auto", "auto-approved",
                    outcome=note, actor="heartbeat")
    return f"logged: {note}"


def run_cycle() -> dict:
    """One heartbeat: gather → decide → act → log. Returns the cycle summary."""
    global _carry_state
    with _lock:
        started = datetime.now(timezone.utc).isoformat()
        try:
            decision, _carry_state = watcher.gather_and_decide(_carry_state)
        except audit.AuditWriteError as exc:
            # Standing order: audit failure halts autonomous action.
            logger.error("heartbeat halted: %s", exc)
            return {"ts": started, "halted": str(exc)}

        results = [_apply_action(a) for a in decision.get("actions", [])]
        for task_id in decision.get("due_task_ids", []):
            tasks.mark_ran(task_id)

        summary = {
            "ts": started,
            "assessment": decision.get("assessment", ""),
            "decided_by": decision.get("decided_by", ""),
            "findings": decision.get("findings", []),
            "results": results,
        }
        try:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATUS_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        except OSError:
            pass
        return summary


def last_status() -> dict:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"ts": None, "assessment": "no heartbeat has run yet"}


def start() -> None:
    """Start the background heartbeat scheduler (idempotent)."""
    global _scheduler
    if _scheduler is not None or config.HEARTBEAT_MINUTES <= 0:
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(run_cycle, "interval",
                       minutes=config.HEARTBEAT_MINUTES,
                       id="remy-heartbeat", coalesce=True, max_instances=1)
    _scheduler.start()
    logger.info("Heartbeat started: every %s min", config.HEARTBEAT_MINUTES)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
