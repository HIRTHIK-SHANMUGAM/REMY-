"""
Permission engine — the code-level gate every tool call passes through.

This runs at the point of invocation, regardless of what any model "decided".
Order of checks:
  1. Hard denylist (destructive shell patterns, system paths) → refuse outright.
  2. Path allowlist for filesystem-touching args → escalate to approval if outside.
  3. Tier dispatch: AUTO runs, LOGGED runs + audits, REQUIRES_APPROVAL blocks
     on the approval queue until the user confirms (or it expires → denied).
  4. Every branch writes an audit entry; if the audit log is unwritable the
     action is refused (fail closed).
"""

import functools
import inspect
import re
from pathlib import Path
from typing import Any, Callable

from remy.config import config
from remy.permissions.tiers import RiskTier, tier_for
from remy.permissions import audit, approvals


class PermissionDenied(Exception):
    """Raised when an action is refused; message is safe to show the model."""


# ── hard denylist: refused even inside the workspace, even if "approved" ──

DESTRUCTIVE_SHELL_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b",  # rm -rf / -fr
    r"\brm\s+-[rRf]+\s+[/~]",          # rm -r on root/home
    r"\bmkfs(\.\w+)?\b",               # formatting filesystems
    r"\bdd\s+.*of=/dev/",              # raw writes to devices
    r">\s*/dev/sd[a-z]",
    r"\bdiskpart\b|\bformat\s+[a-z]:",  # Windows disk formatting
    r":\(\)\s*\{.*\};\s*:",            # fork bomb
    r"\bshutdown\b|\breboot\b|\bhalt\b",
    r"\bchmod\s+(-R\s+)?777\s+/",
    r"\bcurl\b.*\|\s*(ba)?sh|\bwget\b.*\|\s*(ba)?sh",  # pipe-to-shell installs
    r"del\s+/[sq]\s+", r"\brmdir\s+/s\b",              # Windows recursive delete
    r"\bsudo\b",
]

# Shell commands that only read state → may run in the LOGGED tier.
_SAFE_SHELL_PREFIXES = (
    "ls", "dir", "cat", "type ", "head", "tail", "grep", "find ", "findstr",
    "pwd", "cd ", "echo", "whoami", "date", "df", "du", "ps", "top -l",
    "git status", "git log", "git diff", "git branch", "which", "where ",
    "python --version", "pip list", "uname", "hostname", "wc ", "stat ",
)

_PATH_ARG_NAMES = {"path", "file_path", "source", "destination", "directory", "cwd"}

# Browser navigation patterns that always require user approval: auth pages
# and anything financial. Matched against "host/path" (lowercased) with
# fnmatch-style wildcards.
BROWSER_APPROVAL_PATTERNS = [
    "*google.com/accounts*",
    "*accounts.google.com*",
    "*github.com/login*",
    "*bank*",
    "*paypal.com*",
]


def url_requires_approval(url: str) -> tuple[bool, str]:
    """True if navigating to this URL needs explicit user approval."""
    from fnmatch import fnmatch
    from urllib.parse import urlparse
    parsed = urlparse(url if "://" in url else f"https://{url}")
    target = f"{parsed.netloc}{parsed.path}".lower()
    for pattern in BROWSER_APPROVAL_PATTERNS:
        if fnmatch(target, pattern):
            return True, f"URL matches auth/financial pattern `{pattern}`"
    return False, ""


def check_shell_command(command: str) -> tuple[str, str]:
    """
    Classify a shell command. Returns (verdict, why) where verdict is one of
    'deny', 'logged', 'approval'.
    """
    lowered = command.strip().lower()
    for pattern in DESTRUCTIVE_SHELL_PATTERNS:
        if re.search(pattern, lowered):
            return "deny", f"matches destructive pattern `{pattern}`"
    if any(lowered.startswith(p) for p in _SAFE_SHELL_PREFIXES):
        return "logged", "read-only command"
    return "approval", "shell command that may modify state"


def is_path_allowed(raw: str | Path) -> bool:
    """True iff the (resolved) path is inside an allowlisted directory."""
    try:
        p = Path(raw).expanduser().resolve()
    except (OSError, ValueError):
        return False
    return any(p == d or p.is_relative_to(d) for d in config.ALLOWED_DIRS)


def _path_violations(args: dict[str, Any]) -> list[str]:
    return [
        f"{k}={v!r} is outside the allowed workspace"
        for k, v in args.items()
        if k in _PATH_ARG_NAMES and isinstance(v, (str, Path)) and v
        and not is_path_allowed(v)
    ]


# ── the gate ─────────────────────────────────────────────────────────

def authorize(tool_name: str, args: dict[str, Any], actor: str = "user-session") -> str:
    """
    Run all checks for a tool call. Returns the audit `decision` string on
    success; raises PermissionDenied otherwise. Blocks on user approval when
    the effective tier is REQUIRES_APPROVAL.
    """
    tier = tier_for(tool_name)
    escalation_reason = ""

    # 1. Shell-specific hard checks
    if tool_name == "run_shell":
        verdict, why = check_shell_command(str(args.get("command", "")))
        if verdict == "deny":
            audit.log_event(tool_name, args, tier.value, "blocked",
                            outcome=f"refused: {why}", actor=actor)
            raise PermissionDenied(
                f"Refused: this command {why}. This is a hard rule (RULES.md); "
                f"it will not run even with approval.")
        if verdict == "approval":
            tier, escalation_reason = RiskTier.REQUIRES_APPROVAL, why

    # 1b. Browser navigation to auth/financial sites → approval
    if tool_name == "navigate_to":
        needs, why = url_requires_approval(str(args.get("url", "")))
        if needs:
            tier, escalation_reason = RiskTier.REQUIRES_APPROVAL, why

    # 2. Filesystem allowlist — out-of-workspace paths escalate to approval
    violations = _path_violations(args)
    if violations and tier != RiskTier.REQUIRES_APPROVAL:
        tier, escalation_reason = RiskTier.REQUIRES_APPROVAL, "; ".join(violations)

    # 3. Tier dispatch
    if tier == RiskTier.AUTO:
        audit.log_event(tool_name, args, tier.value, "auto-approved", actor=actor)
        return "auto-approved"

    if tier == RiskTier.LOGGED:
        audit.log_event(tool_name, args, tier.value, "logged", actor=actor)
        return "logged"

    # REQUIRES_APPROVAL — queue it and block
    reason = escalation_reason or "high-risk action per permission policy"
    req_id = approvals.create_request(tool_name, args, reason, actor)
    audit.log_event(tool_name, args, tier.value, "approval-requested",
                    outcome=f"request {req_id}: {reason}", actor=actor)
    verdict = approvals.wait_for_verdict(req_id)
    if verdict == "approved":
        audit.log_event(tool_name, args, tier.value, "approved-by-user",
                        outcome=f"request {req_id}", actor=actor)
        return "approved-by-user"
    audit.log_event(tool_name, args, tier.value, "denied",
                    outcome=f"request {req_id} {verdict}", actor=actor)
    raise PermissionDenied(
        f"Action '{tool_name}' was {verdict} "
        f"({'user declined' if verdict == 'denied' else 'no user response'}). "
        f"Do not retry it unchanged; explain the situation to the user.")


def guarded(fn: Callable, tool_name: str | None = None) -> Callable:
    """
    Wrap a tool function so every invocation passes through authorize() and
    the result/outcome is audited. Preserves the signature for FastMCP schema
    generation. Works for sync and async tools.
    """
    name = tool_name or fn.__name__

    def _record_result(result: Any) -> None:
        audit.log_event(name, {}, tier_for(name).value, "completed",
                        outcome=str(result)[:300])

    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def async_wrapper(*a, **kw):
            bound = inspect.signature(fn).bind(*a, **kw)
            bound.apply_defaults()
            try:
                authorize(name, dict(bound.arguments))
            except PermissionDenied as exc:
                return f"[PERMISSION] {exc}"
            except audit.AuditWriteError as exc:
                return f"[HALTED] {exc}"
            result = await fn(*a, **kw)
            _record_result(result)
            return result
        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*a, **kw):
        bound = inspect.signature(fn).bind(*a, **kw)
        bound.apply_defaults()
        try:
            authorize(name, dict(bound.arguments))
        except PermissionDenied as exc:
            return f"[PERMISSION] {exc}"
        except audit.AuditWriteError as exc:
            return f"[HALTED] {exc}"
        result = fn(*a, **kw)
        _record_result(result)
        return result
    return sync_wrapper
