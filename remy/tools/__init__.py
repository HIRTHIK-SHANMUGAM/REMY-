"""
Tool registry — every tool module registers through the permission guard.

`guard` is remy.permissions.guarded: it wraps each tool implementation so the
authorize() gate and audit log run on every invocation, regardless of which
agent (or which model) asked for the call.
"""

from remy.permissions import guarded
from remy.tools import (
    apps,
    filesystem,
    input as input_tools,
    memory_tools,
    personality_tools,
    scheduler,
    screen,
    shell,
    system,
    utils,
    web,
)

ALL_MODULES = [
    web, system, utils,
    filesystem, shell, apps, input_tools, screen,
    scheduler, memory_tools, personality_tools,
]


def register_all_tools(mcp):
    """Register all tool groups onto the MCP server instance."""
    for module in ALL_MODULES:
        module.register(mcp, guarded)
