"""
Browser agent — carries out web tasks delegated by the Orchestrator
(e.g. "find me a flight to Paris on July 20").

Executor-style bounded tool loop restricted to the browser tool set. Flow for
a research/booking task: navigate → wait/extract/links → screenshot+describe
only when visuals are blocking → record_task_outcome on completion → report a
structured result back for the Orchestrator to synthesize.
"""

from remy.agents import base, toolbox
from remy.config import config
from remy.identity import build_system_prompt

ROLE = """
# ROLE: BROWSER AGENT

You are REMY's browser sub-agent. You receive one concrete web task and carry
it out with the browser tools, then report back.
- Prefer extract_text / get_page_links for reading pages; use
  screenshot_and_describe with is_visual_blocking=true ONLY when you cannot
  proceed without understanding the visuals (it costs tokens).
- If a tool returns [PERMISSION], the site needs user approval (auth or
  financial page) — report that verbatim and stop; do NOT retry unchanged.
- Never enter credentials or payment details yourself.
- When you complete a booking/submission/purchase step, immediately call
  record_task_outcome with the concrete result (ids, confirmation numbers,
  dates, prices).
- Finish with a structured report: what you found or did, options with
  prices/times where relevant, and any confirmation details.
""".strip()

BROWSER_TOOLS = {
    "navigate_to", "fill_form", "click_element", "extract_text",
    "screenshot_and_describe", "get_page_links", "wait_for_element",
    "get_current_url", "record_task_outcome",
}

MAX_STEPS = 12


def run_browser_task(instruction: str) -> str:
    """Execute a delegated web task; returns the agent's final report."""
    system = build_system_prompt(ROLE)
    tools = [t for t in toolbox.mcp_tool_schemas() if t["name"] in BROWSER_TOOLS]
    messages: list[dict] = [{"role": "user", "content": instruction}]

    for _ in range(MAX_STEPS):
        resp = base.complete_with_tools(
            config.EXECUTOR_MODEL, system, messages, tools, temperature=0.2)
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        text = "".join(b.text for b in resp.content if b.type == "text")
        if not tool_uses:
            return text or "(browser agent finished with no report)"

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for tu in tool_uses:
            output = toolbox.call_tool(tu.name, tu.input or {})
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": str(output)[:8000]})
        messages.append({"role": "user", "content": results})

    return "Browser agent stopped: step limit reached before the task completed."
