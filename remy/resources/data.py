"""
Data resources — REMY's identity files and live state exposed via MCP.
"""

import json

from remy import tasks
from remy.identity import load_identity_file
from remy.permissions import audit
from remy.personality import Personality


def register(mcp):

    @mcp.resource("remy://info")
    def server_info() -> str:
        """Returns basic info about this MCP server."""
        return (
            "REMY MCP Server\n"
            "A local-first, autonomous desktop AI agent.\n"
            "Built with FastMCP. All tool calls pass a code-enforced "
            "permission layer and are audit-logged."
        )

    @mcp.resource("remy://identity")
    def identity() -> str:
        """REMY's IDENTITY.md."""
        return load_identity_file("IDENTITY.md")

    @mcp.resource("remy://rules")
    def rules() -> str:
        """REMY's RULES.md — hard boundaries."""
        return load_identity_file("RULES.md")

    @mcp.resource("remy://standing-orders")
    def standing_orders() -> str:
        """REMY's STANDING_ORDERS.md."""
        return load_identity_file("STANDING_ORDERS.md")

    @mcp.resource("remy://personality")
    def personality() -> str:
        """Current personality dials as JSON."""
        return json.dumps(Personality.load().as_dict(), indent=2)

    @mcp.resource("remy://audit/recent")
    def recent_audit() -> str:
        """Last 50 audit log entries."""
        return json.dumps(audit.read_recent(50), indent=2)

    @mcp.resource("remy://tasks")
    def scheduled_tasks() -> str:
        """Pending scheduled tasks."""
        return json.dumps(tasks.list_tasks(), indent=2)
