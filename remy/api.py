"""
REMY local web API + dashboard host.

FastAPI app bound to localhost (config.BIND_HOST) serving:
  - the HUD dashboard (desktop/ui) that the Tauri shell wraps
  - chat endpoint → Orchestrator
  - approvals (list / approve / deny) — the blocking side of the permission layer
  - personality dials, audit log, tasks, heartbeat status/trigger

Run: python -m remy.api   (the Tauri shell launches this automatically)
"""

import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from remy import heartbeat, tasks
from remy.config import PROJECT_ROOT, config
from remy.permissions import approvals, audit
from remy.personality import Personality, TRAITS
from remy.tools.system import get_health_snapshot

logging.basicConfig(level=logging.INFO)

UI_DIR = PROJECT_ROOT / "desktop" / "ui"

app = FastAPI(title="REMY", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup() -> None:
    heartbeat.start()


@app.on_event("shutdown")
def _shutdown() -> None:
    heartbeat.stop()


# ── chat ─────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str


@app.post("/api/chat")
def chat(body: ChatMessage):
    from remy.agents import orchestrator
    reply = orchestrator.handle_message(body.message)
    return {"reply": reply}


@app.post("/api/chat/reset")
def chat_reset():
    from remy.agents import orchestrator
    orchestrator.reset_history()
    return {"ok": True}


# ── state for the dashboard ──────────────────────────────────────────

@app.get("/api/state")
def state():
    return {
        "name": config.SERVER_NAME,
        "user": config.USER_NAME,
        "health": get_health_snapshot(),
        "personality": Personality.load().as_dict(),
        "traits": [{"key": t.key, "label": t.label} for t in TRAITS],
        "pending_approvals": approvals.pending_requests(),
        "tasks": tasks.list_tasks(),
        "heartbeat": heartbeat.last_status(),
        "heartbeat_minutes": config.HEARTBEAT_MINUTES,
        "memory": _memory_state(),
        "audit": audit.read_recent(40),
    }


def _memory_state() -> dict:
    try:
        from remy.memory.tiered import get_memory
        return get_memory().state()
    except Exception as exc:
        return {"error": str(exc)}


# ── approvals ────────────────────────────────────────────────────────

class Verdict(BaseModel):
    approve: bool


@app.post("/api/approvals/{req_id}")
def resolve_approval(req_id: str, body: Verdict):
    ok = approvals.resolve(req_id, body.approve)
    return {"ok": ok}


# ── personality ──────────────────────────────────────────────────────

class TraitUpdate(BaseModel):
    values: dict[str, int]


@app.post("/api/personality")
def set_personality(body: TraitUpdate):
    p = Personality.load()
    errors = []
    for key, pct in body.values.items():
        try:
            p.set(key, pct)
        except KeyError as exc:
            errors.append(str(exc))
    p.save()
    return {"personality": p.as_dict(), "errors": errors}


# ── tasks ────────────────────────────────────────────────────────────

class NewTask(BaseModel):
    description: str
    due_at: str | None = None
    recur_minutes: int | None = None


@app.post("/api/tasks")
def create_task(body: NewTask):
    return tasks.add_task(body.description, body.due_at, body.recur_minutes,
                          created_by="user")


@app.delete("/api/tasks/{task_id}")
def cancel_task(task_id: str):
    return {"ok": tasks.set_status(task_id, "cancelled")}


# ── heartbeat ────────────────────────────────────────────────────────

@app.post("/api/heartbeat/run")
def run_heartbeat_now():
    return heartbeat.run_cycle()


# ── UI ───────────────────────────────────────────────────────────────

@app.get("/")
def index():
    index_file = UI_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"remy": "online", "ui": "not built"})


if (UI_DIR / "index.html").exists() or UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")


def main():
    # Local-only binding by default — never expose beyond localhost without
    # the user explicitly changing REMY_BIND_HOST (see RULES.md).
    uvicorn.run(app, host=config.BIND_HOST, port=config.API_PORT, log_level="info")


if __name__ == "__main__":
    main()
