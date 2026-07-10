"""
Watcher — the sub-agent behind the heartbeat loop.

Every cycle it gathers state (health, due tasks, standing-order findings),
then *decides* what to do. The decision step uses the cheap Watcher model
when available; without any model it falls back to the coded standing-order
actions alone, so autonomy never silently dies — it just gets less clever.
"""

import json

from remy import standing_orders, tasks
from remy.agents import base
from remy.config import config
from remy.identity import build_system_prompt

ROLE = """
# ROLE: WATCHER

You are REMY's Watcher sub-agent, running an autonomous heartbeat with no user
present. You receive a state snapshot: system health, standing-order findings,
and tasks that are due. Decide what needs doing.

Respond with STRICT JSON only:
{
  "assessment": "<one sentence>",
  "actions": [
    {"kind": "notify_user", "message": "..."} |
    {"kind": "execute", "instruction": "<concrete task for the Executor>"} |
    {"kind": "log_only", "note": "..."}
  ]
}

Rules: prefer log_only when nothing truly needs attention. Use execute only
for clearly useful, low-risk work (the permission layer will still gate it).
Anything ambiguous or user-facing → notify_user, never act silently.
""".strip()


def decide(findings: list[standing_orders.Finding],
           due: list[dict], health: dict) -> dict:
    """LLM decision over the snapshot; coded fallback when no model is available."""
    snapshot = {
        "health": health,
        "standing_order_findings": [f.as_dict() for f in findings],
        "due_tasks": due,
    }
    try:
        reply = base.complete(
            config.WATCHER_MODEL,
            build_system_prompt(ROLE),
            [{"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)}],
            max_tokens=800,
            temperature=0.2,
        )
        start, end = reply.find("{"), reply.rfind("}")
        decision = json.loads(reply[start:end + 1])
        decision.setdefault("actions", [])
        decision["decided_by"] = config.WATCHER_MODEL
        return decision
    except (base.LLMUnavailable, json.JSONDecodeError, ValueError):
        return _coded_fallback(findings, due)


def _coded_fallback(findings: list[standing_orders.Finding], due: list[dict]) -> dict:
    actions = []
    for f in findings:
        if f.escalate:
            actions.append({"kind": "notify_user",
                            "message": f"{f.condition}: {f.detail} — {f.action}"})
        else:
            actions.append({"kind": "log_only", "note": f"{f.condition}: {f.detail}"})
    for t in due:
        actions.append({"kind": "notify_user",
                        "message": f"Task due: {t['description']} (id {t['id']})"})
    if not actions:
        actions.append({"kind": "log_only", "note": "heartbeat: nothing to do"})
    return {"assessment": "rule-based evaluation (no model available)",
            "actions": actions, "decided_by": "coded-fallback"}


def gather_and_decide(previous_state: dict | None = None) -> tuple[dict, dict]:
    """One full Watcher pass: gather → decide. Returns (decision, carry_state)."""
    findings, state = standing_orders.evaluate(previous_state)
    due = tasks.due_tasks()
    decision = decide(findings, due, state["health"])
    decision["findings"] = [f.as_dict() for f in findings]
    decision["due_task_ids"] = [t["id"] for t in due]
    return decision, state
