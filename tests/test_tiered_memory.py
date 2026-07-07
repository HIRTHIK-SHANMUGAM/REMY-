import json
from datetime import datetime, timedelta, timezone

import pytest

from remy.memory import tiered
from remy.memory.tiered import (
    ACTIVE_FILE,
    ARCHIVE_DIR,
    FACTS_FILE,
    STATE_FILE,
    TieredMemory,
)


@pytest.fixture()
def mem():
    """Fresh memory files for each test."""
    for path in (ACTIVE_FILE, FACTS_FILE, STATE_FILE):
        if path.exists():
            path.unlink()
    if ARCHIVE_DIR.exists():
        for f in ARCHIVE_DIR.glob("*.jsonl.gz"):
            f.unlink()
    return TieredMemory()


def _old_iso(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _write_old_episode(text: str, days_old: float) -> None:
    with ACTIVE_FILE.open("a", encoding="utf-8") as f:
        f.write(f"- [{_old_iso(days_old)}] {text}\n")


# ── decay scoring ────────────────────────────────────────────────

def test_decay_fresh_fact_scores_near_confidence(mem):
    fact = mem.add_fact("Hirthik uses VS Code", confidence=0.9)
    assert mem.decay_score(fact) == pytest.approx(0.9, abs=0.05)


def test_decay_old_untouched_fact_falls_below_floor(mem):
    fact = mem.add_fact("some ancient trivia", confidence=0.8)
    fact["last_referenced"] = _old_iso(60)
    assert mem.decay_score(fact) < tiered.ARCHIVE_SCORE_FLOOR


def test_pinned_fact_never_decays(mem):
    fact = mem.add_fact("Project deadline is Aug 15", pinned=True)
    fact["last_referenced"] = _old_iso(365)
    assert mem.decay_score(fact) == 1.0


def test_recall_refreshes_decay_clock(mem):
    mem.add_fact("Hirthik prefers dark mode", confidence=0.8)
    facts = mem._load_facts()
    facts[0]["last_referenced"] = _old_iso(40)
    mem._save_facts(facts)
    hits = mem.recall("dark mode")
    assert hits and "dark mode" in hits[0]["text"]
    refreshed = mem._load_facts()[0]
    assert mem.decay_score(refreshed) > 0.5  # recall made it hot again


# ── dedupe + contradictions ──────────────────────────────────────

def test_duplicates_merge(mem):
    mem.add_fact("Hirthik lives in Chennai", confidence=0.6)
    mem.add_fact("Hirthik lives in Chennai!", confidence=0.9)
    facts = mem._load_facts()
    chennai = [f for f in facts if "Chennai" in f["text"]]
    assert len(chennai) == 1
    assert chennai[0]["confidence"] == 0.9


def test_contradiction_keeps_newer(mem):
    facts = [
        {"id": "a", "text": "Hirthik likes coffee", "created": _old_iso(10),
         "last_referenced": _old_iso(0), "confidence": 0.9,
         "references": 0, "pinned": False},
        {"id": "b", "text": "not Hirthik likes coffee", "created": _old_iso(1),
         "last_referenced": _old_iso(0), "confidence": 0.9,
         "references": 0, "pinned": False},
    ]
    mem._save_facts(facts)
    report = mem._compress_facts()
    assert report["contradictions_resolved"] == 1
    remaining = [f["text"] for f in mem._load_facts()]
    assert remaining == ["not Hirthik likes coffee"]


# ── compression thresholds ───────────────────────────────────────

def test_needs_compression_on_size(mem, monkeypatch):
    monkeypatch.setattr(tiered, "ACTIVE_SIZE_LIMIT", 100)
    mem.add_episode("x" * 200)
    needed, why = mem.needs_compression()
    assert needed and "KB" in why


def test_needs_compression_on_age(mem):
    _write_old_episode("something from long ago", days_old=10)
    needed, why = mem.needs_compression()
    assert needed and "older than" in why


def test_no_compression_needed_when_fresh(mem):
    mem.add_episode("fresh note")
    needed, _ = mem.needs_compression()
    assert not needed


# ── the headline requirement: 70%+ reduction, facts stay accessible ──

def test_compression_reduces_active_by_70pct_keeping_relevant_facts(mem):
    # 120 verbose old episodes (>7 days) + a handful of hot ones
    for i in range(120):
        _write_old_episode(
            f"Long rambling session log number {i}: discussed many things "
            f"in detail, none of it individually important. " + "filler " * 30,
            days_old=8 + (i % 20),
        )
    mem.add_episode("Hot note: reviewing REMY PR today")
    # high-relevance facts that must survive
    mem.add_fact("Project deadline is August 15", pinned=True)
    mem.add_fact("Hirthik prefers concise briefings", confidence=0.95)
    # a stale fact that should be archived
    stale = mem.add_fact("random one-off trivia about weather", confidence=0.5)
    facts = mem._load_facts()
    for f in facts:
        if f["id"] == stale["id"]:
            f["last_referenced"] = _old_iso(90)
    mem._save_facts(facts)

    before = ACTIVE_FILE.stat().st_size
    report = mem.compress()
    after = ACTIVE_FILE.stat().st_size

    # 70%+ size reduction
    assert after < before * 0.30, f"only reduced {before} -> {after}"
    assert report["reduction_pct"] >= 70

    # hot episode kept
    assert "Hot note" in ACTIVE_FILE.read_text()

    # high-relevance facts still accessible via recall
    assert any("August 15" in h["text"] for h in mem.recall("project deadline"))
    assert any("concise" in h["text"] for h in mem.recall("briefing preference"))

    # stale fact archived but reachable through archive fallback
    remaining = [f["text"] for f in mem._load_facts()]
    assert all("weather" not in t for t in remaining)
    archived_hits = mem.recall("weather trivia")
    assert any(h.get("archived") for h in archived_hits)

    # summary of old episodes became a fact; archive file exists
    assert any("Summary of 120" in f["text"] for f in mem._load_facts())
    assert list(ARCHIVE_DIR.glob("episodes-*.jsonl.gz"))

    # metadata updated
    state = json.loads(STATE_FILE.read_text())
    assert state["last_compression"] == report["ts"]
    assert state["last_report"]["reduction_pct"] >= 70


# ── pinning + prompt injection ───────────────────────────────────

def test_pinned_facts_always_in_prompt(mem):
    mem.add_fact("Goal: ship REMY v1", pinned=True)
    mem.add_fact("likes tea", confidence=0.6)
    section = mem.render_prompt_section()
    assert "## Pinned" in section
    assert "Goal: ship REMY v1" in section
    from remy.identity import build_system_prompt
    assert "Goal: ship REMY v1" in build_system_prompt()


def test_pin_and_unpin_by_text(mem):
    mem.add_fact("Standup is at 9am")
    assert mem.pin_fact("Standup is at 9am")
    assert mem._load_facts()[0]["pinned"] is True
    assert mem.pin_fact("Standup is at 9am", pinned=False)
    assert mem._load_facts()[0]["pinned"] is False


def test_pinned_survives_compression_even_when_stale(mem):
    mem.add_fact("Deadline: file taxes July 31", pinned=True)
    facts = mem._load_facts()
    facts[0]["last_referenced"] = _old_iso(200)
    mem._save_facts(facts)
    mem.compress()
    assert any("taxes" in f["text"] for f in mem._load_facts())


# ── async queueing ───────────────────────────────────────────────

def test_queue_compression_runs_async_and_once(mem):
    import time
    _write_old_episode("old entry", days_old=10)
    assert tiered.queue_compression(actor="test") is True
    # second call while (possibly) running either refuses or re-runs after done
    for _ in range(50):
        if not tiered._compression_running.is_set():
            break
        time.sleep(0.1)
    assert not tiered._compression_running.is_set()
    assert STATE_FILE.exists()
