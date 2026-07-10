"""
Personality tools — read/adjust REMY's expression dials (all 0–100%).
Changes persist and apply from the very next reply.
"""

import json

from remy.personality import Personality, TRAITS


def register(mcp, guard):

    @mcp.tool()
    def get_personality_settings() -> str:
        """Show REMY's current personality dials (each 0–100%)."""
        def impl() -> str:
            p = Personality.load()
            rows = [
                f"- {t.label} ({t.key}): {p.values[t.key]}%"
                for t in TRAITS
            ]
            return "Current personality settings:\n" + "\n".join(rows)
        return guard(impl, "get_personality_settings")()

    @mcp.tool()
    def set_personality_trait(trait: str, percent: int) -> str:
        """
        Set a personality trait to a percentage (0–100). Traits: humour,
        emotion, seriousness, sarcasm, formality, verbosity, proactivity, empathy.
        """
        def impl(trait: str, percent: int) -> str:
            p = Personality.load()
            try:
                p.set(trait.strip().lower(), percent)
            except KeyError as exc:
                return str(exc)
            p.save()
            return (f"{trait} set to {p.values[trait.strip().lower()]}%. "
                    f"Now: {json.dumps(p.as_dict())}")
        return guard(impl, "set_personality_trait")(trait, percent)
