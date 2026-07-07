"""
Risk tiers and tool classification.

Every tool is assigned a tier here, at registration time — not by the LLM.
Unknown tools default to REQUIRES_APPROVAL: fail closed, never open.
"""

from enum import Enum


class RiskTier(str, Enum):
    AUTO = "auto"                     # read-only / low-risk: runs immediately
    LOGGED = "logged"                 # writes within allowlisted paths: runs, always audited
    REQUIRES_APPROVAL = "approval"    # blocks until the user explicitly confirms


# Tool name → tier. The single authoritative map.
TOOL_TIERS: dict[str, RiskTier] = {
    # ── read-only / informational ──
    "get_current_time": RiskTier.AUTO,
    "get_system_info": RiskTier.AUTO,
    "get_system_health": RiskTier.AUTO,
    "get_world_news": RiskTier.AUTO,
    "get_world_finance_news": RiskTier.AUTO,
    "search_web": RiskTier.AUTO,
    "fetch_url": RiskTier.AUTO,
    "format_json": RiskTier.AUTO,
    "word_count": RiskTier.AUTO,
    "read_file": RiskTier.AUTO,
    "list_directory": RiskTier.AUTO,
    "search_files": RiskTier.AUTO,
    "list_scheduled_tasks": RiskTier.AUTO,
    "get_personality_settings": RiskTier.AUTO,
    "recall_memory": RiskTier.AUTO,
    "memory_status": RiskTier.AUTO,
    "capture_screen": RiskTier.AUTO,
    "describe_screen": RiskTier.AUTO,
    "list_open_apps": RiskTier.AUTO,

    # ── writes inside the allowlist / benign local actions ──
    "write_file": RiskTier.LOGGED,
    "append_file": RiskTier.LOGGED,
    "create_directory": RiskTier.LOGGED,
    "run_shell": RiskTier.LOGGED,          # engine may still escalate (see engine.py)
    "open_world_monitor": RiskTier.LOGGED,
    "open_finance_world_monitor": RiskTier.LOGGED,
    "open_app": RiskTier.LOGGED,
    "schedule_task": RiskTier.LOGGED,
    "cancel_scheduled_task": RiskTier.LOGGED,
    "remember_fact": RiskTier.LOGGED,
    "pin_memory": RiskTier.LOGGED,
    "set_personality_trait": RiskTier.LOGGED,

    # ── high-risk: explicit user approval, every time ──
    "delete_file": RiskTier.REQUIRES_APPROVAL,
    "move_file": RiskTier.REQUIRES_APPROVAL,   # can overwrite/relocate outside intent
    "close_app": RiskTier.REQUIRES_APPROVAL,   # can lose unsaved work
    "type_text": RiskTier.REQUIRES_APPROVAL,
    "press_keys": RiskTier.REQUIRES_APPROVAL,
    "click_mouse": RiskTier.REQUIRES_APPROVAL,
    "move_mouse": RiskTier.REQUIRES_APPROVAL,
}


def tier_for(tool_name: str) -> RiskTier:
    """Fail closed: unknown tools require approval."""
    return TOOL_TIERS.get(tool_name, RiskTier.REQUIRES_APPROVAL)
