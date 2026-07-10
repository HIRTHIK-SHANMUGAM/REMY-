"""
Permission / sandbox layer — code-enforced, not prompt-enforced.

Public surface:
    guarded(fn)          — wrap a tool so every call is authorized + audited
    authorize(...)       — the raw gate (used by sub-agents directly)
    PermissionDenied     — raised/returned when an action is refused
    RiskTier, tier_for   — tier classification
"""

from remy.permissions.engine import guarded, authorize, PermissionDenied
from remy.permissions.tiers import RiskTier, tier_for

__all__ = ["guarded", "authorize", "PermissionDenied", "RiskTier", "tier_for"]
