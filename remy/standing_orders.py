"""
Standing orders engine — coded evaluation of the STANDING_ORDERS.md table.

Deterministic conditions (disk, CPU, overdue tasks, stale approvals) are
checked in code every heartbeat; ambiguous situations are escalated to the
Watcher model for judgment. Each finding carries the matched order,
recommended action, and escalate flag.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from remy import tasks
from remy.permissions import approvals
from remy.tools.system import get_health_snapshot

DISK_FREE_THRESHOLD = 10.0     # percent
CPU_HIGH_THRESHOLD = 90.0      # percent
TASK_OVERDUE_HOURS = 24
APPROVAL_STALE_MINUTES = 60


@dataclass
class Finding:
    condition: str
    action: str
    escalate: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"condition": self.condition, "action": self.action,
                "escalate": self.escalate, "detail": self.detail}


def evaluate(previous_state: dict | None = None) -> tuple[list[Finding], dict]:
    """
    Run all coded standing-order checks. Returns (findings, state) where state
    carries values the next cycle needs (e.g. sustained-CPU tracking).
    """
    findings: list[Finding] = []
    prev = previous_state or {}
    health = get_health_snapshot()
    state = {"health": health}

    # Disk free space < 10% → alert user (escalate)
    disk_free = health.get("disk_free_percent")
    if disk_free is not None and disk_free < DISK_FREE_THRESHOLD:
        findings.append(Finding(
            "Disk free space < 10%",
            "Alert user via notification",
            escalate=True,
            detail=f"{disk_free}% free"))

    # CPU sustained > 90% across cycles → note first, alert if it persists
    cpu = health.get("cpu_percent")
    cpu_high = cpu is not None and cpu > CPU_HIGH_THRESHOLD
    state["cpu_high"] = cpu_high
    if cpu_high:
        persisted = prev.get("cpu_high", False)
        findings.append(Finding(
            "CPU sustained > 90%",
            "Alert user" if persisted else "Note in log; alert if it persists",
            escalate=persisted,
            detail=f"cpu={cpu}%"))

    # Scheduled task overdue > 24h → remind user
    for t in tasks.overdue_tasks(hours=TASK_OVERDUE_HOURS):
        findings.append(Finding(
            "Scheduled task overdue > 24h",
            "Remind user",
            escalate=False,
            detail=f"task {t['id']}: {t['description']}"))

    # Pending approval older than 1h → re-surface
    now = datetime.now(timezone.utc)
    for req in approvals.pending_requests():
        try:
            age = now - datetime.fromisoformat(req["ts"])
        except ValueError:
            continue
        if age > timedelta(minutes=APPROVAL_STALE_MINUTES):
            findings.append(Finding(
                "Pending approval request older than 1h",
                "Re-surface the approval to the user",
                escalate=False,
                detail=f"request {req['id']}: {req['tool']}"))

    return findings, state
