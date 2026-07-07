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

# Conversation history — durable across restarts (plain text turns only;
# tool-use exchanges stay within a single handle_message call).
HISTORY_FILE = None


def _history_file():
    global HISTORY_FILE
    if HISTORY_FILE is None:
        from remy.config import DATA_DIR
        HISTORY_FILE = DATA_DIR / "chat_history.jsonl"
    return HISTORY_FILE


def _load_history(limit: int = 200) -> list[dict]:
    import json
    path = _history_file()
    if not path.exists():
        return []
    turns = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            turn = json.loads(line)
            if turn.get("role") in ("user", "assistant") and isinstance(
                    turn.get("content"), str):
                turns.append({"role": turn["role"], "content": turn["content"]})
        except json.JSONDecodeError:
            continue
    return turns


def _persist_turn(role: str, content: str) -> None:
    import json
    path = _history_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"role": role, "content": content},
                           ensure_ascii=False) + "\n")


_history: list[dict] = _load_history()


def reset_history() -> None:
    _history.clear()
    path = _history_file()
    if path.exists():
        path.unlink()


def handle_message(user_message: str) -> str:
    """Main chat entry point used by the API/dashboard."""
    system = build_system_prompt(ROLE)
    try:
        tools = toolbox.mcp_tool_schemas() + [DELEGATE_TOOL]
    except Exception:
        tools = [DELEGATE_TOOL]

    _history.append({"role": "user", "content": user_message})
    _persist_turn("user", user_message)
    messages = _history[-40:]  # bounded context (slice = working copy)

    try:
        for _ in range(MAX_STEPS):
            resp = base.complete_with_tools(
                config.ORCHESTRATOR_MODEL, system, messages, tools)
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            text = "".join(b.text for b in resp.content if b.type == "text")
            if not tool_uses:
                _history.append({"role": "assistant", "content": text})
                _persist_turn("assistant", text)
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
        _persist_turn("assistant", final)
        return final

    except base.LLMUnavailable as exc:
        return (f"My reasoning engine isn't configured yet ({exc}). "
                "Set ANTHROPIC_API_KEY in .env to bring me fully online — "
                "the dashboard, permission layer, and heartbeat still work.")
