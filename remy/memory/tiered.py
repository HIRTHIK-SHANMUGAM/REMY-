"""
Tiered, self-pruning, auto-compressing memory.

Layout (under remy_data/memory/):
  ACTIVE_MEMORY.md      — hot episodic memory, newest last, loaded into prompts
  SEMANTIC_FACTS.jsonl  — extracted knowledge with decay scoring
  MEMORY_STATE.json     — metadata: sizes, counts, last compression
  .memory_archive/      — gzip-compressed pruned episodes and decayed facts

Compression pipeline (run by the heartbeat when thresholds hit, or manually):
  1. Episodic entries older than EPISODIC_HOT_DAYS are summarized (LLM when
     available, extractive fallback otherwise), the summary is kept as a fact,
     and the raw entries move to the archive.
  2. Facts are re-scored with decay; unpinned facts under ARCHIVE_SCORE_FLOOR
     are archived.
  3. Duplicates are merged (keep highest confidence, sum references) and naive
     contradictions ("X" vs "not X") resolved in favour of the newer fact.
  4. MEMORY_STATE.json is updated.

Pinned facts never decay and are always injected into the system prompt.
"""

import gzip
import json
import math
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from remy.config import DATA_DIR

MEMORY_DIR = DATA_DIR / "memory"
ACTIVE_FILE = MEMORY_DIR / "ACTIVE_MEMORY.md"
FACTS_FILE = MEMORY_DIR / "SEMANTIC_FACTS.jsonl"
STATE_FILE = MEMORY_DIR / "MEMORY_STATE.json"
ARCHIVE_DIR = MEMORY_DIR / ".memory_archive"

# Compression thresholds / tuning
ACTIVE_SIZE_LIMIT = 500 * 1024        # bytes: compress when ACTIVE_MEMORY exceeds
EPISODIC_HOT_DAYS = 7                 # episodes older than this get summarized
ARCHIVE_SCORE_FLOOR = 0.3             # unpinned facts below this are archived
DECAY_HALF_LIFE_DAYS = 14.0           # reference-recency half-life
PROMPT_ACTIVE_TAIL = 30               # recent episodes injected into prompts
PROMPT_FACT_LIMIT = 20                # top-scored facts injected into prompts

_ENTRY_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2}T[\d:.+Z-]+)\] ?(.*)$")

_lock = threading.RLock()
_compression_running = threading.Event()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(raw: str) -> datetime:
    try:
        ts = datetime.fromisoformat(raw)
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return _now()


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


_NEGATIONS = ("not ", "no ", "never ", "doesnt ", "dont ", "isnt ")


def _denegate(norm: str) -> tuple[str, bool]:
    """Strip a leading negation token; returns (base, was_negated)."""
    for neg in _NEGATIONS:
        if norm.startswith(neg):
            return norm[len(neg):].strip(), True
    return norm, False


class TieredMemory:
    def __init__(self) -> None:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # ── writing ──────────────────────────────────────────────────

    def add_episode(self, text: str) -> None:
        with _lock:
            with ACTIVE_FILE.open("a", encoding="utf-8") as f:
                f.write(f"- [{_now().isoformat()}] {text.strip()}\n")

    def add_fact(self, text: str, confidence: float = 0.8,
                 pinned: bool = False) -> dict:
        """Add a semantic fact; exact-duplicate texts merge instead of piling up."""
        text = text.strip()
        norm = _normalize(text)
        with _lock:
            facts = self._load_facts()
            for fact in facts:
                if _normalize(fact["text"]) == norm:
                    fact["confidence"] = max(fact["confidence"], confidence)
                    fact["references"] = fact.get("references", 0) + 1
                    fact["last_referenced"] = _now().isoformat()
                    fact["pinned"] = fact.get("pinned", False) or pinned
                    self._save_facts(facts)
                    return fact
            fact = {
                "id": uuid.uuid4().hex[:10],
                "text": text,
                "created": _now().isoformat(),
                "last_referenced": _now().isoformat(),
                "confidence": max(0.0, min(1.0, confidence)),
                "references": 0,
                "pinned": bool(pinned),
            }
            facts.append(fact)
            self._save_facts(facts)
            return fact

    def pin_fact(self, fact_id_or_text: str, pinned: bool = True) -> bool:
        with _lock:
            facts = self._load_facts()
            needle = _normalize(fact_id_or_text)
            for fact in facts:
                if fact["id"] == fact_id_or_text or _normalize(fact["text"]) == needle:
                    fact["pinned"] = pinned
                    self._save_facts(facts)
                    return True
        return False

    # ── decay scoring ────────────────────────────────────────────

    @staticmethod
    def decay_score(fact: dict, now: datetime | None = None) -> float:
        """
        Relevance in [0, 1]. Pinned facts never decay.
        score = confidence × 0.5^(days_since_last_reference / half_life)
                × (1 + reference bonus), clamped.
        Age matters through last_referenced: an old fact that keeps being
        recalled stays hot; an old fact nobody touches decays away.
        """
        if fact.get("pinned"):
            return 1.0
        now = now or _now()
        ref_days = max(0.0, (now - _parse_ts(fact.get(
            "last_referenced", fact.get("created", now.isoformat())))
        ).total_seconds() / 86400)
        recency = 0.5 ** (ref_days / DECAY_HALF_LIFE_DAYS)
        ref_bonus = 1.0 + min(0.5, 0.1 * math.log1p(fact.get("references", 0)))
        return max(0.0, min(1.0, fact.get("confidence", 0.5) * recency * ref_bonus))

    # ── compression ──────────────────────────────────────────────

    def needs_compression(self) -> tuple[bool, str]:
        size = ACTIVE_FILE.stat().st_size if ACTIVE_FILE.exists() else 0
        if size > ACTIVE_SIZE_LIMIT:
            return True, f"ACTIVE_MEMORY is {size // 1024}KB (> {ACTIVE_SIZE_LIMIT // 1024}KB)"
        oldest = self._oldest_active_ts()
        if oldest and _now() - oldest > timedelta(days=EPISODIC_HOT_DAYS):
            return True, f"episodic entries older than {EPISODIC_HOT_DAYS} days present"
        return False, "within thresholds"

    def compress(self) -> dict:
        """Run the full compression pipeline. Returns a report dict."""
        with _lock:
            report: dict[str, Any] = {"ts": _now().isoformat()}
            before = ACTIVE_FILE.stat().st_size if ACTIVE_FILE.exists() else 0

            report["episodic"] = self._compress_episodic()
            report["facts"] = self._compress_facts()

            after = ACTIVE_FILE.stat().st_size if ACTIVE_FILE.exists() else 0
            report["active_bytes_before"] = before
            report["active_bytes_after"] = after
            report["reduction_pct"] = round(100 * (1 - after / before), 1) if before else 0.0
            self._write_state(last_compression=report["ts"],
                              last_report=report)
            return report

    def _compress_episodic(self) -> dict:
        """Summarize + archive episodes older than EPISODIC_HOT_DAYS."""
        entries = self._load_active()
        cutoff = _now() - timedelta(days=EPISODIC_HOT_DAYS)
        old = [(ts, txt) for ts, txt in entries if ts < cutoff]
        hot = [(ts, txt) for ts, txt in entries if ts >= cutoff]
        if not old:
            return {"summarized": 0, "kept_hot": len(hot)}

        summary = self._summarize([txt for _, txt in old])
        # summary becomes a durable semantic fact, raw entries go to archive
        self.add_fact(f"Summary of {len(old)} older memories: {summary}",
                      confidence=0.7)
        self._archive("episodes", [
            {"ts": ts.isoformat(), "text": txt} for ts, txt in old
        ])
        self._save_active(hot)
        return {"summarized": len(old), "kept_hot": len(hot),
                "summary_chars": len(summary)}

    def _compress_facts(self) -> dict:
        """Dedupe, resolve contradictions, archive low-relevance facts."""
        facts = self._load_facts()
        now = _now()

        # 1. merge duplicates by normalized text
        merged: dict[str, dict] = {}
        dupes = 0
        for fact in facts:
            key = _normalize(fact["text"])
            if key in merged:
                keep = merged[key]
                keep["confidence"] = max(keep["confidence"], fact["confidence"])
                keep["references"] = keep.get("references", 0) + fact.get("references", 0)
                keep["pinned"] = keep.get("pinned") or fact.get("pinned", False)
                keep["last_referenced"] = max(keep["last_referenced"],
                                              fact["last_referenced"])
                dupes += 1
            else:
                merged[key] = dict(fact)

        # 2. naive contradiction cleanup: "X" vs "not X" → keep the newer one
        contradictions = 0
        by_base: dict[str, list[tuple[str, bool]]] = {}
        for key in merged:
            base, negated = _denegate(key)
            by_base.setdefault(base, []).append((key, negated))
        for base, variants in by_base.items():
            if len(variants) > 1 and any(n for _, n in variants) \
                    and any(not n for _, n in variants):
                keep_key = max(variants,
                               key=lambda v: merged[v[0]]["created"])[0]
                for key, _ in variants:
                    if key != keep_key and not merged[key].get("pinned"):
                        merged[key]["_contradicted"] = True
                        contradictions += 1

        # 3. archive contradicted + low-score (never pinned) facts
        keep, drop = [], []
        for fact in merged.values():
            score = self.decay_score(fact, now)
            fact["score"] = round(score, 3)
            if fact.pop("_contradicted", False) or \
                    (not fact.get("pinned") and score < ARCHIVE_SCORE_FLOOR):
                drop.append(fact)
            else:
                keep.append(fact)
        if drop:
            self._archive("facts", drop)
        self._save_facts(keep)
        return {"kept": len(keep), "archived": len(drop),
                "duplicates_merged": dupes, "contradictions_resolved": contradictions}

    def _summarize(self, texts: list[str]) -> str:
        """LLM summary when configured; extractive fallback otherwise."""
        joined = "\n".join(f"- {t}" for t in texts)
        try:
            from remy.agents import base
            from remy.config import config
            return base.complete(
                config.WATCHER_MODEL,
                "Compress these memory entries into at most 5 bullet lines, "
                "keeping every durable fact, preference, decision, or deadline. "
                "Drop chit-chat. Output only the bullets.",
                [{"role": "user", "content": joined[:12000]}],
                max_tokens=400, temperature=0.0,
            ).strip()
        except Exception:
            # extractive fallback: first clause of each entry, day-deduplicated
            seen: set[str] = set()
            lines = []
            for t in texts:
                head = t.split(".")[0][:100].strip()
                key = _normalize(head)[:60]
                if key and key not in seen:
                    seen.add(key)
                    lines.append(head)
                if len(lines) >= 10:
                    break
            return "; ".join(lines)

    # ── recall ───────────────────────────────────────────────────

    def recall(self, query: str, limit: int = 5,
               include_archive: bool = True) -> list[dict]:
        """
        Search facts by keyword relevance × decay score. Hits refresh
        last_referenced (recalled facts stay hot). Falls back to the archive
        when the hot tier yields too few results.
        """
        terms = [t for t in _normalize(query).split() if len(t) > 2]
        if not terms:
            return []
        now = _now()
        with _lock:
            facts = self._load_facts()
            scored = []
            for fact in facts:
                norm = _normalize(fact["text"])
                match = sum(1 for t in terms if t in norm) / len(terms)
                if match > 0:
                    scored.append((match * (0.5 + 0.5 * self.decay_score(fact, now)),
                                   fact))
            scored.sort(key=lambda s: -s[0])
            hits = [f for _, f in scored[:limit]]
            for fact in hits:  # recall refreshes the decay clock
                fact["last_referenced"] = now.isoformat()
                fact["references"] = fact.get("references", 0) + 1
            if hits:
                self._save_facts(facts)
        if len(hits) < limit and include_archive:
            for item in self._search_archive(terms, limit - len(hits)):
                item["archived"] = True
                hits.append(item)
        return hits

    def _search_archive(self, terms: list[str], limit: int) -> list[dict]:
        results: list[dict] = []
        for path in sorted(ARCHIVE_DIR.glob("*.jsonl.gz"), reverse=True):
            try:
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    for line in f:
                        item = json.loads(line)
                        norm = _normalize(item.get("text", ""))
                        if any(t in norm for t in terms):
                            results.append(item)
                            if len(results) >= limit:
                                return results
            except (OSError, json.JSONDecodeError):
                continue
        return results

    # ── prompt injection ─────────────────────────────────────────

    def render_prompt_section(self) -> str:
        """Pinned facts + top-relevance facts + recent episodes for prompts."""
        with _lock:
            facts = self._load_facts()
            entries = self._load_active()
        now = _now()
        pinned = [f for f in facts if f.get("pinned")]
        unpinned = sorted((f for f in facts if not f.get("pinned")),
                          key=lambda f: -self.decay_score(f, now))
        lines = ["# MEMORY (tiered — pinned never decays)"]
        if pinned:
            lines.append("\n## Pinned (critical — always true until changed)")
            lines += [f"- {f['text']}" for f in pinned]
        if unpinned:
            lines.append("\n## Known facts (by relevance)")
            lines += [f"- {f['text']}" for f in unpinned[:PROMPT_FACT_LIMIT]]
        if entries:
            lines.append("\n## Recent activity")
            lines += [f"- [{ts.date()}] {txt}"
                      for ts, txt in entries[-PROMPT_ACTIVE_TAIL:]]
        return "\n".join(lines)

    # ── state / io helpers ───────────────────────────────────────

    def state(self) -> dict:
        stored = {}
        if STATE_FILE.exists():
            try:
                stored = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        facts = self._load_facts()
        needed, why = self.needs_compression()
        stored.update({
            "active_bytes": ACTIVE_FILE.stat().st_size if ACTIVE_FILE.exists() else 0,
            "active_entries": len(self._load_active()),
            "fact_count": len(facts),
            "pinned_count": sum(1 for f in facts if f.get("pinned")),
            "archive_files": len(list(ARCHIVE_DIR.glob("*.jsonl.gz"))),
            "compression_needed": needed,
            "compression_reason": why,
        })
        return stored

    def _write_state(self, **updates) -> None:
        state = {}
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        state.update(updates)
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))

    def _load_active(self) -> list[tuple[datetime, str]]:
        if not ACTIVE_FILE.exists():
            return []
        entries = []
        for line in ACTIVE_FILE.read_text(encoding="utf-8").splitlines():
            m = _ENTRY_RE.match(line)
            if m:
                entries.append((_parse_ts(m.group(1)), m.group(2)))
        return entries

    def _save_active(self, entries: list[tuple[datetime, str]]) -> None:
        ACTIVE_FILE.write_text(
            "".join(f"- [{ts.isoformat()}] {txt}\n" for ts, txt in entries),
            encoding="utf-8")

    def _oldest_active_ts(self) -> datetime | None:
        entries = self._load_active()
        return min((ts for ts, _ in entries), default=None)

    def _load_facts(self) -> list[dict]:
        if not FACTS_FILE.exists():
            return []
        facts = []
        for line in FACTS_FILE.read_text(encoding="utf-8").splitlines():
            try:
                facts.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return facts

    def _save_facts(self, facts: list[dict]) -> None:
        FACTS_FILE.write_text(
            "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in facts),
            encoding="utf-8")

    def _archive(self, kind: str, items: list[dict]) -> Path:
        stamp = _now().strftime("%Y%m%d-%H%M%S")
        path = ARCHIVE_DIR / f"{kind}-{stamp}.jsonl.gz"
        with gzip.open(path, "at", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return path


_memory: TieredMemory | None = None


def get_memory() -> TieredMemory:
    global _memory
    if _memory is None:
        _memory = TieredMemory()
    return _memory


def queue_compression(actor: str = "heartbeat") -> bool:
    """
    Run compression on a background thread so it never blocks agent replies.
    Returns False if a compression is already in flight.
    """
    if _compression_running.is_set():
        return False
    _compression_running.set()

    def _run():
        from remy.permissions import audit
        try:
            report = get_memory().compress()
            audit.log_event("memory_compression", {}, "auto", "auto-approved",
                            outcome=json.dumps(report)[:500], actor=actor)
        except Exception as exc:
            try:
                audit.log_event("memory_compression", {}, "auto", "error",
                                outcome=str(exc)[:300], actor=actor)
            except Exception:
                pass
        finally:
            _compression_running.clear()

    threading.Thread(target=_run, daemon=True, name="remy-memory-compress").start()
    return True
