"""
Orchestrator — the REMY the user actually talks to.

Highest-capability model. Decomposes requests, calls tools directly for
simple things, delegates multi-step concrete work to the Executor, and
synthesizes the final reply. Falls back to a clear offline message when no
reasoning model is configured (tools and dashboard still work).
"""

from remy.agents import base, toolbox
from remy.config import config
from remy.identity import build_system_prompt

ROLE = """
# ROLE: ORCHESTRATOR

You are REMY itself — the agent the user converses with.
- Use tools directly for quick lookups and single actions.
- For multi-step concrete work, call delegate_to_executor with a precise,
  self-contained instruction; report its result back naturally.
- If a tool returns [PERMISSION], tell the user what you wanted to do, why it
  needs approval, and that it's waiting on the REMY dashboard. Never retry a
  denied action unchanged.
- Keep replies in your current personality settings.
""".strip()

DELEGATE_TOOL = {
    "name": "delegate_to_executor",
    "description": ("Hand a concrete multi-step task to the Executor sub-agent "
                    "(cheaper model, full tool access via the permission layer). "
                    "Give a precise, self-contained instruction."),
    "input_schema": {
        "type": "object",
        "properties": {"instruction": {"type": "string"}},
        "required": ["instruction"],
    },
}

MAX_STEPS = 10

# Conversation history for the single-user chat session
_history: list[dict] = []


def reset_history() -> None:
    _history.clear()


def handle_message(user_message: str) -> str:
    """Main chat entry point used by the API/dashboard."""
    system = build_system_prompt(ROLE)
    try:
        tools = toolbox.mcp_tool_schemas() + [DELEGATE_TOOL]
    except Exception:
        tools = [DELEGATE_TOOL]

    _history.append({"role": "user", "content": user_message})
    messages = _history[-40:]  # bounded context

    try:
        for _ in range(MAX_STEPS):
            resp = base.complete_with_tools(
                config.ORCHESTRATOR_MODEL, system, messages, tools)
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            text = "".join(b.text for b in resp.content if b.type == "text")
            if not tool_uses:
                _history.append({"role": "assistant", "content": text})
                return text

            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for tu in tool_uses:
                if tu.name == "delegate_to_executor":
                    from remy.agents import executor
                    output = executor.run_task(
                        (tu.input or {}).get("instruction", ""))
                else:
                    output = toolbox.call_tool(tu.name, tu.input or {})
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": str(output)[:8000]})
            messages.append({"role": "user", "content": results})

        final = "I hit my step limit mid-task — here's where things stand; ask me to continue."
        _history.append({"role": "assistant", "content": final})
        return final

    except base.LLMUnavailable as exc:
        return (f"My reasoning engine isn't configured yet ({exc}). "
                "Set ANTHROPIC_API_KEY in .env to bring me fully online — "
                "the dashboard, permission layer, and heartbeat still work.")
