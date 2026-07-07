"""
Memory tools — REMY updates its own memory as it learns, per the identity spec.
"""

from remy.memory import get_store


def register(mcp, guard):

    @mcp.tool()
    def remember_fact(text: str, durable: bool = False) -> str:
        """
        Store something worth remembering. Set durable=True for core facts
        (preferences, decisions) that should load into every future session.
        """
        def impl(text: str, durable: bool = False) -> str:
            return get_store().remember(text, durable=durable)
        return guard(impl, "remember_fact")(text, durable)

    @mcp.tool()
    def recall_memory(query: str, limit: int = 5) -> str:
        """Search past memories semantically (or by keyword fallback)."""
        def impl(query: str, limit: int = 5) -> str:
            hits = get_store().recall(query, limit=limit)
            if not hits:
                return "No matching memories."
            return "\n".join(f"- {h}" for h in hits)
        return guard(impl, "recall_memory")(query, limit)
