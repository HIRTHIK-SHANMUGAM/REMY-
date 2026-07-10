"""
Reviewer — conservative sanity check on actions above the low-risk threshold.

Consulted by the Orchestrator/heartbeat before proposing destructive or
high-impact operations. Advisory only: the code-level permission engine is
the real gate; the Reviewer adds judgment on top of it, never instead of it.
"""

from remy.agents import base
from remy.config import config
from remy.identity import build_system_prompt

ROLE = """
# ROLE: REVIEWER

You are REMY's Reviewer sub-agent — the conservative second opinion.
You are given a proposed action and its justification. Answer with exactly
one line starting with APPROVE or REJECT, then one short sentence of reasoning.
Bias: when in doubt, REJECT. Destructive, irreversible, security-relevant, or
user-communication actions need a clearly stated, proportionate justification.
""".strip()


def review_action(action: str, justification: str) -> tuple[bool, str]:
    """Returns (approved, note). Unavailable model = not approved (fail closed)."""
    try:
        reply = base.complete(
            config.REVIEWER_MODEL,
            build_system_prompt(ROLE),
            [{"role": "user",
              "content": f"Proposed action: {action}\nJustification: {justification}"}],
            max_tokens=200,
            temperature=0.0,
        ).strip()
    except base.LLMUnavailable as exc:
        return False, f"Reviewer unavailable ({exc}) — defaulting to reject."
    approved = reply.upper().startswith("APPROVE")
    return approved, reply
