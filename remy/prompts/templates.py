"""
Reusable prompt templates registered with the MCP server.
"""


def register(mcp):

    @mcp.prompt()
    def summarize(text: str) -> str:
        """Prompt to summarize a block of text."""
        return f"Summarize the following text concisely:\n\n{text}"

    @mcp.prompt()
    def explain_code(code: str, language: str = "Python") -> str:
        """Prompt to explain a block of code."""
        return (
            f"Explain the following {language} code in plain English, "
            f"step by step:\n\n```{language.lower()}\n{code}\n```"
        )

    @mcp.prompt()
    def daily_brief() -> str:
        """Prompt REMY to deliver a morning-style status brief."""
        return (
            "Give a concise status brief: pending scheduled tasks, any standing "
            "order alerts since the last brief, system health, and one line of "
            "world news if available. Keep it under six sentences."
        )
