"""
Executor — carries out concrete actions delegated by the Orchestrator.

Runs a bounded tool-use loop on a faster/cheaper model; the heavy reasoning
already happened upstream. Tool access is still fully mediated by the
permission engine — the Executor holds no special privileges.
"""

from remy.agents import base, toolbox
from remy.config import config
from remy.identity import build_system_prompt

ROLE = """
# ROLE: EXECUTOR

You are REMY's Executor sub-agent. You receive one concrete task from the
Orchestrator and carry it out with the tools available, then report back.
- Do the task, nothing beyond it.
- If a tool returns [PERMISSION], the action needs user approval or was
  refused — report that verbatim; do NOT retry it unchanged.
- Finish with a short factual report of what was done and any outputs.
""".strip()

MAX_STEPS = 8


def run_task(instruction: str, actor: str = "executor") -> str:
    """Execute a delegated task; returns the Executor's final report."""
    system = build_system_prompt(ROLE)
    tools = toolbox.mcp_tool_schemas()
    messages: list[dict] = [{"role": "user", "content": instruction}]

    for _ in range(MAX_STEPS):
        resp = base.complete_with_tools(
            config.EXECUTOR_MODEL, system, messages, tools, temperature=0.2)
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        text = "".join(b.text for b in resp.content if b.type == "text")
        if not tool_uses:
            return text or "(executor finished with no report)"

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for tu in tool_uses:
            output = toolbox.call_tool(tu.name, tu.input or {})
            results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": output[:8000],
            })
        messages.append({"role": "user", "content": results})

    return "Executor stopped: step limit reached before the task completed."
