"""
Scheduler tools — register/list/cancel one-off and recurring tasks.
These back the heartbeat loop: the Watcher picks up due tasks each cycle.
"""

import json

from remy import tasks


def register(mcp, guard):

    @mcp.tool()
    def schedule_task(description: str, due_at: str = "",
                      recur_minutes: int = 0) -> str:
        """
        Schedule a task. due_at is ISO-8601 (empty = as soon as possible);
        recur_minutes > 0 makes it recurring. The heartbeat picks it up.
        """
        def impl(description: str, due_at: str = "", recur_minutes: int = 0) -> str:
            task = tasks.add_task(
                description,
                due_at=due_at or None,
                recur_minutes=recur_minutes or None,
                created_by="agent",
            )
            return f"Scheduled task {task['id']}: {description}"
        return guard(impl, "schedule_task")(description, due_at, recur_minutes)

    @mcp.tool()
    def list_scheduled_tasks(include_closed: bool = False) -> str:
        """List scheduled tasks (pending by default)."""
        def impl(include_closed: bool = False) -> str:
            items = tasks.list_tasks(include_closed=include_closed)
            if not items:
                return "No scheduled tasks."
            return json.dumps(items, indent=2)
        return guard(impl, "list_scheduled_tasks")(include_closed)

    @mcp.tool()
    def cancel_scheduled_task(task_id: str) -> str:
        """Cancel a scheduled task by id."""
        def impl(task_id: str) -> str:
            ok = tasks.set_status(task_id, "cancelled")
            return f"Cancelled {task_id}." if ok else f"No task with id {task_id}."
        return guard(impl, "cancel_scheduled_task")(task_id)
