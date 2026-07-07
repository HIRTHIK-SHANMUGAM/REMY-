"""
Configuration — env vars, paths, and app-wide settings for REMY.

Everything that gates what REMY may touch (bind host, allowed directories)
lives here so the permission layer has a single source of truth.
"""

import os
import platform
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Repo root (…/remy/config.py -> repo)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Runtime state: audit logs, approvals, memory DB, scheduled tasks.
DATA_DIR = Path(os.getenv("REMY_DATA_DIR", PROJECT_ROOT / "remy_data"))

# Identity files shipped with the repo (IDENTITY.md, RULES.md, …)
IDENTITY_DIR = PROJECT_ROOT / "remy" / "identity"


def _default_workspace() -> Path:
    return Path.home() / "RemyWorkspace"


def _parse_allowed_dirs(raw: str) -> list[Path]:
    sep = ";" if platform.system() == "Windows" else ":"
    dirs = [Path(p).expanduser().resolve() for p in raw.split(sep) if p.strip()]
    return dirs or [_default_workspace()]


class Config:
    SERVER_NAME: str = os.getenv("SERVER_NAME", "REMY")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    USER_NAME: str = os.getenv("REMY_USER_NAME", "Hirthik")

    # Network — local-only by default. This is a hard safety default:
    # the MCP server and API must never be exposed beyond localhost
    # without the user explicitly changing REMY_BIND_HOST.
    BIND_HOST: str = os.getenv("REMY_BIND_HOST", "127.0.0.1")
    MCP_PORT: int = int(os.getenv("REMY_MCP_PORT", "8000"))
    API_PORT: int = int(os.getenv("REMY_API_PORT", "8377"))

    # Autonomy loop
    HEARTBEAT_MINUTES: int = int(os.getenv("REMY_HEARTBEAT_MINUTES", "20"))

    # Filesystem allowlist — the only directories write-capable tools may touch.
    ALLOWED_DIRS: list[Path] = _parse_allowed_dirs(os.getenv("REMY_ALLOWED_DIRS", ""))

    # Reasoning engines
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ORCHESTRATOR_MODEL: str = os.getenv("REMY_ORCHESTRATOR_MODEL", "claude-fable-5")
    EXECUTOR_MODEL: str = os.getenv("REMY_EXECUTOR_MODEL", "claude-sonnet-5")
    REVIEWER_MODEL: str = os.getenv("REMY_REVIEWER_MODEL", "claude-sonnet-5")
    WATCHER_MODEL: str = os.getenv("REMY_WATCHER_MODEL", "claude-haiku-4-5-20251001")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

    # External API keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")


config = Config()


def ensure_dirs() -> None:
    """Create runtime directories on first launch."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for d in config.ALLOWED_DIRS:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # non-fatal: dir may be on an unavailable volume


ensure_dirs()
