"""
In-process bridge between sub-agents and the MCP tool layer.

Agents call tools through the same FastMCP instance the voice pipeline uses,
so the permission engine and audit log apply identically no matter which
agent (or model) initiated the call.
"""

import asyncio
import threading
from typing import Any

_mcp = None
_loop: asyncio.AbstractEventLoop | None = None


def _get_mcp():
    global _mcp
    if _mcp is None:
        import server  # instantiates FastMCP and registers all guarded tools
        _mcp = server.mcp
    return _mcp


def _get_loop() -> asyncio.AbstractEventLoop:
    """A dedicated background loop so sync agent code can await tool calls."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        threading.Thread(target=_loop.run_forever, daemon=True,
                         name="remy-toolbox-loop").start()
    return _loop


def mcp_tool_schemas() -> list[dict]:
    """Anthropic-format tool definitions for every registered MCP tool."""
    mcp = _get_mcp()
    fut = asyncio.run_coroutine_threadsafe(mcp.list_tools(), _get_loop())
    tools = fut.result(timeout=30)
    return [
        {
            "name": t.name,
            "description": t.description or t.name,
            "input_schema": t.inputSchema,
        }
        for t in tools
    ]


def call_tool(name: str, args: dict[str, Any], timeout_s: float = 330) -> str:
    """
    Invoke an MCP tool synchronously. Timeout is above the approval-queue
    timeout so blocked high-risk calls can still resolve.
    """
    mcp = _get_mcp()
    fut = asyncio.run_coroutine_threadsafe(mcp.call_tool(name, args), _get_loop())
    try:
        result = fut.result(timeout=timeout_s)
    except Exception as exc:
        return f"[TOOL ERROR] {name}: {exc}"
    parts = []
    for item in result:
        text = getattr(item, "text", None)
        parts.append(text if text is not None else str(item))
    return "\n".join(parts) if parts else "(no output)"
