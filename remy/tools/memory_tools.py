"""
Memory tools — REMY updates its own memory as it learns, per the identity spec.
Backed by the tiered self-pruning store (ACTIVE_MEMORY.md + SEMANTIC_FACTS.jsonl
+ compressed archive); the Chroma episodic store is kept in sync when available.
"""

from remy.memory import get_store
from remy.memory.tiered import get_memory


def register(mcp, guard):

    @mcp.tool()
    def remember_fact(text: str, durable: bool = False, pinned: bool = False,
                      confidence: float = 0.8) -> str:
        """
        Store something worth remembering. durable=True also appends to
        MEMORY.md; pinned=True marks it critical (deadlines, goals, user
        preferences) — pinned facts never decay and always load into prompts.
        """
        def impl(text: str, durable: bool = False, pinned: bool = False,
                 confidence: float = 0.8) -> str:
            mem = get_memory()
            mem.add_episode(text)
            fact = mem.add_fact(text, confidence=confidence, pinned=pinned)
            try:
                get_store().remember(text, durable=durable)  # vector index
            except Exception:
                pass
            return (f"Remembered (fact {fact['id']}"
                    f"{', pinned' if fact['pinned'] else ''}"
                    f"{', durable' if durable else ''}).")
        return guard(impl, "remember_fact")(text, durable, pinned, confidence)

    @mcp.tool()
    def recall_memory(query: str, limit: int = 5) -> str:
        """Search memory: hot facts first (decay-weighted), archive fallback."""
        def impl(query: str, limit: int = 5) -> str:
            hits = get_memory().recall(query, limit=limit)
            if not hits:
                vector_hits = []
                try:
                    vector_hits = get_store().recall(query, limit=limit)
                except Exception:
                    pass
                if not vector_hits:
                    return "No matching memories."
                return "\n".join(f"- {h}" for h in vector_hits)
            return "\n".join(
                f"- {h['text']}" + (" [archived]" if h.get("archived") else "")
                for h in hits)
        return guard(impl, "recall_memory")(query, limit)

    @mcp.tool()
    def pin_memory(fact: str, pinned: bool = True) -> str:
        """Pin (or unpin) a fact by id or text so it never decays."""
        def impl(fact: str, pinned: bool = True) -> str:
            ok = get_memory().pin_fact(fact, pinned=pinned)
            if ok:
                return f"Fact {'pinned' if pinned else 'unpinned'}."
            return "No matching fact found — store it first with remember_fact."
        return guard(impl, "pin_memory")(fact, pinned)

    @mcp.tool()
    def memory_status() -> str:
        """Report memory-system state: sizes, counts, compression status."""
        def impl() -> str:
            import json
            return json.dumps(get_memory().state(), indent=2)
        return guard(impl, "memory_status")()
