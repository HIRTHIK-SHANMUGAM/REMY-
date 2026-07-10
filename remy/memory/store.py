"""
Long-term memory — two layers, per the architecture:

1. Structured core: MEMORY.md (always loaded into the system prompt) — durable
   facts, preferences, decisions. Appended via remember_fact.
2. Semantic recall: a Chroma vector store in remy_data/memory/ for episodic
   memories searchable by meaning. Falls back to keyword search over a JSONL
   file when chromadb isn't installed, so memory always works.
"""

import json
import threading
from datetime import datetime, timezone

from remy.config import DATA_DIR
from remy.identity import append_memory

MEMORY_DIR = DATA_DIR / "memory"
EPISODES_FILE = MEMORY_DIR / "episodes.jsonl"

_lock = threading.Lock()


class MemoryStore:
    def __init__(self) -> None:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._collection = None
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(MEMORY_DIR / "chroma"))
            self._collection = client.get_or_create_collection("remy_memory")
        except Exception:
            self._collection = None  # keyword fallback

    @property
    def backend(self) -> str:
        return "chroma" if self._collection is not None else "keyword-jsonl"

    # ── writing ──────────────────────────────────────────────────

    def remember(self, text: str, kind: str = "fact", durable: bool = False) -> str:
        """
        Store a memory. durable=True also appends to MEMORY.md so it is loaded
        into every future system prompt.
        """
        ts = datetime.now(timezone.utc).isoformat()
        entry = {"ts": ts, "kind": kind, "text": text}
        with _lock:
            with EPISODES_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if self._collection is not None:
            try:
                self._collection.add(
                    documents=[text],
                    metadatas=[{"ts": ts, "kind": kind}],
                    ids=[f"{ts}-{abs(hash(text)) % 10**8}"],
                )
            except Exception:
                pass  # episodic JSONL already has it
        if durable:
            append_memory(f"- ({ts[:10]}) {text}")
        return f"Remembered ({'durable' if durable else 'episodic'}, {self.backend})."

    # ── recall ───────────────────────────────────────────────────

    def recall(self, query: str, limit: int = 5) -> list[str]:
        if self._collection is not None:
            try:
                res = self._collection.query(query_texts=[query], n_results=limit)
                docs = res.get("documents") or [[]]
                if docs[0]:
                    return docs[0]
            except Exception:
                pass
        return self._keyword_recall(query, limit)

    def _keyword_recall(self, query: str, limit: int) -> list[str]:
        if not EPISODES_FILE.exists():
            return []
        terms = [t for t in query.lower().split() if len(t) > 2]
        scored: list[tuple[int, str]] = []
        with _lock:
            lines = EPISODES_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = entry.get("text", "")
            score = sum(1 for t in terms if t in text.lower())
            if score:
                scored.append((score, f"[{entry.get('ts', '')[:10]}] {text}"))
        scored.sort(key=lambda s: -s[0])
        return [t for _, t in scored[:limit]]


_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
