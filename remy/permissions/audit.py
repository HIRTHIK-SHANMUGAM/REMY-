"""
Audit log — append-only JSONL record of every tool call REMY makes.

Non-negotiable: no autonomous action without a corresponding entry. If the
audit log cannot be written, the permission engine refuses the action
(fail closed — see STANDING_ORDERS.md).
"""

import json
import threading
from datetime import datetime, timezone
from typing import Any

from remy.config import DATA_DIR

AUDIT_FILE = DATA_DIR / "audit.jsonl"

_lock = threading.Lock()


class AuditWriteError(RuntimeError):
    """Raised when the audit log cannot be written — halts the action."""


def _serialize_args(args: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in args.items():
        s = repr(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
        if isinstance(s, str) and len(s) > 500:
            s = s[:500] + f"…(+{len(s) - 500} chars)"
        out[k] = s
    return out


def log_event(
    tool: str,
    args: dict[str, Any],
    tier: str,
    decision: str,           # auto-approved | logged | approved-by-user | denied | blocked | error
    outcome: str = "",
    actor: str = "user-session",   # user-session | heartbeat | orchestrator | executor | watcher
    reasoning: str = "",
) -> dict[str, Any]:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "tool": tool,
        "args": _serialize_args(args),
        "tier": tier,
        "decision": decision,
        "outcome": (outcome or "")[:1000],
        "reasoning": (reasoning or "")[:500],
    }
    line = json.dumps(entry, ensure_ascii=False)
    try:
        with _lock:
            AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with AUDIT_FILE.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError as exc:
        raise AuditWriteError(f"Audit log unwritable ({exc}); action halted.") from exc
    return entry


def read_recent(limit: int = 100) -> list[dict[str, Any]]:
    if not AUDIT_FILE.exists():
        return []
    with _lock:
        lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries[::-1]  # newest first
