"""
Utility tools — text processing, formatting, calculations.
"""

import json


def register(mcp, guard):

    @mcp.tool()
    def format_json(data: str) -> str:
        """Pretty-print a JSON string."""
        def impl(data: str) -> str:
            try:
                return json.dumps(json.loads(data), indent=2)
            except json.JSONDecodeError as e:
                return f"Invalid JSON: {e}"
        return guard(impl, "format_json")(data)

    @mcp.tool()
    def word_count(text: str) -> dict:
        """Count words, characters, and lines in a block of text."""
        def impl(text: str) -> dict:
            return {
                "characters": len(text),
                "words": len(text.split()),
                "lines": len(text.splitlines()),
            }
        return guard(impl, "word_count")(text)
