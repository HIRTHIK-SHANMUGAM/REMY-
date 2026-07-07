"""
Identity loader — assembles REMY's full system prompt from the identity files
plus the live personality settings. Injected on every LLM call so edits to the
markdown files or personality sliders take effect immediately.
"""

from pathlib import Path

from remy.config import IDENTITY_DIR
from remy.personality import get_personality

IDENTITY_FILES = ["IDENTITY.md", "RULES.md", "MEMORY.md", "STANDING_ORDERS.md"]


def _read(name: str) -> str:
    path = IDENTITY_DIR / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return f"({name} unavailable)"


def load_identity_file(name: str) -> str:
    if name not in IDENTITY_FILES:
        raise KeyError(f"Unknown identity file: {name}")
    return _read(name)


def append_memory(section_line: str) -> None:
    """Append a durable fact to MEMORY.md (used by the memory tools)."""
    path = IDENTITY_DIR / "MEMORY.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n{section_line.strip()}\n")


def build_system_prompt(role_addendum: str = "") -> str:
    """
    Full system prompt: identity + rules + memory + standing orders +
    live personality dials + optional per-agent role addendum.
    """
    parts = [_read(name) for name in IDENTITY_FILES]
    parts.append(get_personality().render_prompt_section())
    try:
        from remy.memory.tiered import get_memory
        section = get_memory().render_prompt_section()
        if section.count("\n"):  # skip the bare header when memory is empty
            parts.append(section)
    except Exception:
        pass  # memory must never break prompt assembly
    if role_addendum:
        parts.append(role_addendum.strip())
    return "\n\n---\n\n".join(parts)
