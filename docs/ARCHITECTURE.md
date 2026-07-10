# REMY — Architecture

## Design principles

1. **Local-first.** Everything binds to `127.0.0.1`. State (memory, audit,
   approvals, tasks, personality) is plain files under `remy_data/` —
   inspectable, greppable, yours.
2. **Enforcement in code, persuasion in prompts.** RULES.md tells the model
   the boundaries; `remy/permissions/` *enforces* them at the point of tool
   invocation. Prompt injection can fool a model; it cannot skip
   `authorize()`.
3. **Autonomy with a paper trail.** The heartbeat may act without a user
   present, but never without an audit entry. If auditing fails, autonomy
   halts (fail closed).
4. **Graceful degradation.** No API key → coded-fallback heartbeat, working
   dashboard, working permission layer. No chromadb → keyword memory. No
   pyautogui → input tools return a clear install hint. Nothing silently dies.

## Process model

- `python -m remy.api` — the main resident process: FastAPI (dashboard, chat,
  approvals) + APScheduler heartbeat + in-process MCP toolbox for the agents.
- `python server.py` — optional standalone MCP server (SSE :8000) used by the
  LiveKit voice agent. Same tool modules, same permission engine; approvals
  resolved on the dashboard propagate via the shared `approvals.json`
  (file-polled, so cross-process works).
- `desktop/` — Tauri shell that spawns `remy.api`, shows the HUD, and keeps
  REMY alive in the tray when the window closes.

## Call path of every tool invocation

```
model picks tool → toolbox/MCP → guarded(fn)
  → authorize(tool, args)
      → hard denylist (run_shell patterns)        → PermissionDenied
      → path allowlist (config.ALLOWED_DIRS)      → escalate tier
      → tier: AUTO   → audit → run
             LOGGED  → audit → run
             APPROVAL→ audit → queue → notify → BLOCK → user verdict
  → run fn → audit outcome
```

Tier assignments live in one place: `remy/permissions/tiers.py`. Unknown
tools default to REQUIRES_APPROVAL.

## Heartbeat cycle (`remy/heartbeat.py`)

1. Wake on interval (`REMY_HEARTBEAT_MINUTES`, default 20).
2. Gather: health snapshot, standing-order findings
   (`remy/standing_orders.py` — coded checks mirroring STANDING_ORDERS.md),
   due tasks.
3. Decide: Watcher model (cheap; Ollama-capable) returns strict JSON —
   `notify_user` / `execute` / `log_only`. No model → coded fallback.
4. Act: `execute` actions are first screened by the Reviewer (fail-closed),
   then run by the Executor through the permission layer.
5. Log: every cycle writes audit entries (actor=heartbeat) and a status
   snapshot (`remy_data/heartbeat.json`) for the dashboard.

## Multi-agent split (`remy/agents/`)

| Agent | Model (default) | Job | Notes |
|---|---|---|---|
| Orchestrator | claude-fable-5 | user conversation, decomposition, delegation | bounded 10-step tool loop |
| Executor | claude-sonnet-5 | concrete delegated tasks | bounded 8-step loop, temp 0.2 |
| Browser agent | claude-sonnet-5 | delegated web tasks (search, forms, bookings) | browser tool subset only, 12-step loop |
| Watcher | claude-haiku / ollama:* | heartbeat judgment | strict-JSON decisions, coded fallback |
| Reviewer | claude-sonnet-5 | advisory gate on autonomous work | temp 0, rejects on doubt or unavailability |

### Browser automation (`remy/tools/browser.py`)

Playwright Chromium owned by a single dedicated thread (sync API is neither
event-loop- nor thread-safe); tools submit closures and wait. Safeguards:
- `navigate_to` to auth/financial URL patterns (`*google.com/accounts*`,
  `*github.com/login*`, `*bank*`, `*paypal.com*`) escalates to user approval
  in the permission engine.
- First visit to any new domain is audit-logged and the user notified.
- Form fills/clicks are audited with full args; every action also lands in
  ACTIVE_MEMORY, and `record_task_outcome` stores completed bookings/
  submissions as 0.95-confidence semantic facts.
- `screenshot_and_describe` only calls the vision model when
  `is_visual_blocking=true` (token cost gate).
The Orchestrator delegates web tasks via `delegate_to_browser` (e.g. "find a
flight to Paris on July 20") and synthesizes the agent's structured report.

All agents share one system-prompt builder (`remy/identity/build_system_prompt`)
= IDENTITY + RULES + MEMORY + STANDING_ORDERS + live personality dials +
role addendum, so identity and boundaries are uniform.

## Memory

- **Core (always loaded):** `remy/identity/MEMORY.md`, appended via the
  `remember_fact(durable=True)` tool.
- **Tiered self-pruning store** (`remy/memory/tiered.py`), under
  `remy_data/memory/`:
  - `ACTIVE_MEMORY.md` — hot episodic entries, recent tail injected into
    every system prompt.
  - `SEMANTIC_FACTS.jsonl` — extracted knowledge with decay scoring
    (`confidence × 0.5^(days_since_referenced/14) × reference bonus`);
    recall refreshes the decay clock, so used facts stay hot.
  - `MEMORY_STATE.json` — sizes, counts, last compression report.
  - `.memory_archive/` — gzip archives of summarized episodes and decayed
    facts; recall falls back here when the hot tier comes up short.
  - **Pinning:** facts marked `pinned` (deadlines, goals, preferences) never
    decay and are always in the prompt (`pin_memory` tool).
  - **Compression** (heartbeat-triggered when active memory >500KB or
    episodes >7 days old; runs on a background thread so it never blocks
    replies): summarizes old episodes into a fact (LLM or extractive
    fallback), archives facts scoring <0.3, merges duplicates, resolves
    "X"/"not X" contradictions in favour of the newer fact.
- **Episodic vector index:** Chroma collection (keyword fallback) kept in
  sync by `remember_fact` for semantic recall.
- **Conversation:** chat turns persist to `remy_data/chat_history.jsonl` and
  reload on restart (last 200 turns), so REMY picks up where it left off.

## Personality

`remy/personality.py`: eight 0–100% traits with low/high anchor descriptions,
persisted to `remy_data/personality.json`, rendered into every system prompt.
Adjustable from dashboard sliders, chat ("set sarcasm to 70%"), the
`set_personality_trait` tool, or `POST /api/personality`. Explicitly scoped:
dials shape expression, never permissions.

## Known gaps

- Voice pipeline still requires LiveKit cloud credentials (as inherited from
  the FRIDAY foundation); a fully local STT/TTS path is future work.
- Release bundles (`cargo tauri build`) must be produced on each target OS;
  CI currently runs the Python test suite on Linux/Windows/macOS.
