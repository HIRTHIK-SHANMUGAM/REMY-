"""
Personality engine — Hirthik's adjustable dials for how REMY expresses itself.

Every trait is a 0–100 percentage. Settings persist to remy_data/personality.json
and are rendered into the system prompt on every LLM call, so a slider change
takes effect on the very next reply. Traits shape *expression only* — they can
never loosen RULES.md or the permission layer.
"""

import json
import threading
from dataclasses import dataclass, field

from remy.config import DATA_DIR

PERSONALITY_FILE = DATA_DIR / "personality.json"

_lock = threading.Lock()


@dataclass(frozen=True)
class Trait:
    key: str
    label: str
    default: int
    low_desc: str   # behaviour near 0%
    high_desc: str  # behaviour near 100%


TRAITS: list[Trait] = [
    Trait("humour", "Humour", 40,
          "no jokes, purely matter-of-fact",
          "constant wit, playful one-liners in nearly every reply"),
    Trait("emotion", "Emotional warmth", 50,
          "detached and neutral, no emotional colouring",
          "openly warm, empathetic, emotionally expressive"),
    Trait("seriousness", "Seriousness", 60,
          "breezy and casual about everything",
          "gravely professional, treats every topic with full weight"),
    Trait("sarcasm", "Sarcasm / dryness", 30,
          "entirely earnest, zero irony",
          "heavily dry and sardonic, FRIDAY-at-3am energy"),
    Trait("formality", "Formality", 35,
          "slangy, first-name, fully informal",
          "crisp, buttoned-up, almost military brevity"),
    Trait("verbosity", "Verbosity", 40,
          "terse one-liners only",
          "rich, detailed, fully elaborated answers"),
    Trait("proactivity", "Proactivity / initiative", 55,
          "answers only what was asked, suggests nothing",
          "constantly volunteers observations, follow-ups, and offers to act"),
    Trait("empathy", "Empathy", 50,
          "task-focused, ignores the user's mood",
          "highly attuned to mood, checks in, adapts tone to how the user feels"),
]

_TRAIT_BY_KEY = {t.key: t for t in TRAITS}


@dataclass
class Personality:
    values: dict[str, int] = field(
        default_factory=lambda: {t.key: t.default for t in TRAITS}
    )

    def set(self, key: str, percent: int) -> None:
        if key not in _TRAIT_BY_KEY:
            raise KeyError(f"Unknown personality trait: {key!r}. "
                           f"Valid traits: {sorted(_TRAIT_BY_KEY)}")
        self.values[key] = max(0, min(100, int(percent)))

    def as_dict(self) -> dict[str, int]:
        return dict(self.values)

    # ── persistence ──────────────────────────────────────────────

    def save(self) -> None:
        with _lock:
            PERSONALITY_FILE.parent.mkdir(parents=True, exist_ok=True)
            PERSONALITY_FILE.write_text(json.dumps(self.values, indent=2))

    @classmethod
    def load(cls) -> "Personality":
        p = cls()
        if PERSONALITY_FILE.exists():
            try:
                stored = json.loads(PERSONALITY_FILE.read_text())
                for k, v in stored.items():
                    if k in _TRAIT_BY_KEY:
                        p.values[k] = max(0, min(100, int(v)))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass  # corrupt file → fall back to defaults
        return p

    # ── prompt rendering ─────────────────────────────────────────

    def _band(self, pct: int) -> str:
        if pct <= 15:
            return "minimal"
        if pct <= 40:
            return "low"
        if pct <= 60:
            return "moderate"
        if pct <= 85:
            return "high"
        return "maximum"

    def render_prompt_section(self) -> str:
        """Render the current dials as a system-prompt section."""
        lines = [
            "# PERSONALITY SETTINGS (user-adjustable dials — obey them)",
            "",
            "Each trait below is set as a percentage. 0% means the first "
            "description, 100% means the second; blend proportionally in between. "
            "These shape tone and expression only — they never override RULES.",
            "",
        ]
        for t in TRAITS:
            pct = self.values[t.key]
            lines.append(
                f"- **{t.label}: {pct}%** ({self._band(pct)}) — "
                f"0% = {t.low_desc}; 100% = {t.high_desc}."
            )
        return "\n".join(lines)


def get_personality() -> Personality:
    """Load the current persisted personality (cheap; call per prompt build)."""
    return Personality.load()
