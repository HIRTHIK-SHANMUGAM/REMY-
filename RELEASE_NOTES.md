# REMY v1.0.1 — Autonomous Desktop AI Agent

## ✅ What's New

- **Working chat UI** — brand-new frontend built with React + TypeScript +
  Vite + Tailwind CSS (Mobbin-inspired design): markdown rendering, typing
  indicator, live online/offline status, mobile-friendly.
- **No more startup race** — the desktop app now loads the chat UI from
  bundled local assets instantly (no "can't reach this page" flash) while the
  Python backend boots; the UI shows Connecting → Online as it comes up.
- **Backend serves the UI** — `http://localhost:8377` now serves the actual
  chat interface (not a JSON placeholder). The advanced HUD dashboard
  (personality dials, approvals, audit log, heartbeat) moved to
  `http://localhost:8377/hud`.
- **Sturdier app lifecycle** — the app reuses an already-running backend
  instead of double-spawning, and on Linux the backend is reaped even if the
  app is force-killed.

## ✨ Features (from v1.0.0, now much nicer to use)

- **Autonomous heartbeat**: REMY wakes on its own (default every 20 min),
  evaluates standing orders and scheduled tasks, and acts through the
  permission layer.
- **Self-pruning tiered memory**: learns across sessions; old episodic data
  auto-summarizes and compresses; pinned facts never decay.
- **Multi-agent orchestration**: Orchestrator / Executor / Watcher / Reviewer
  roles, all behind the same permission gate.
- **Browser automation**: navigate, read pages, fill forms, screenshots
  (Playwright) with auth/financial-site protection.
- **Desktop control**: file/shell/app access with code-enforced permission
  tiers — risky actions block for your approval.
- **Full audit logging**: every action recorded; autonomy halts if the audit
  log can't be written.
- **Voice + text**: optional LiveKit STT/TTS pipeline.
- **Native packaging**: Windows / macOS / Linux installers.

## 📥 Install

| Platform | Steps |
|---|---|
| **Windows** | Download `remy-*-windows-*.msi` → double-click → Install → launch REMY from the Start menu |
| **macOS** (Apple Silicon) | Download `remy-*-macos-*.dmg` → drag REMY to Applications → launch |
| **Linux** | Download `remy-*-linux-*.AppImage` → `chmod +x` → run (or install the `.deb`) |

Verify downloads against `SHA256SUMS.txt`.

## ⚙️ One-time backend setup (required)

The installers ship the desktop shell; REMY's brain is a Python service the
app starts for you. It needs **Python ≥ 3.11** once:

```bash
pip install "remy[llm,memory,desktop,browser] @ git+https://github.com/hirthik-shanmugam/remy-.git"
```

Then add your `ANTHROPIC_API_KEY` to the `.env` (see `.env.example`) to bring
the reasoning engine online. Without a key, REMY still runs the chat shell,
HUD, permission layer, and rule-based heartbeat — LLM reasoning switches on
when the key is added.

## 🚀 First run

1. Launch REMY — the chat window opens immediately with a Connecting badge.
2. Within a few seconds the badge turns **Online** (backend ready).
3. Type "hello" — REMY responds in the window.
4. The same chat is available in your browser at `http://localhost:8377`;
   the advanced HUD is at `http://localhost:8377/hud` (also via tray →
   **Settings**).

## 📝 Notes

- **Unsigned builds**: Windows SmartScreen → "More info → Run anyway";
  macOS → right-click → Open.
- **Tray behaviour**: closing the window keeps REMY (and its heartbeat)
  running; **Quit** from the tray stops the app *and* the backend.
- **Logs**: lifecycle in `remy_data/app.log`, full action audit in
  `remy_data/audit.jsonl` (also visible on the HUD).
- **Local-only**: everything binds to localhost; your data, memory, and file
  access stay on your machine. Only LLM calls go to the Claude API.

## 🎯 Next (v1.1+)

- Bundled Python runtime (true zero-setup install)
- Intel-mac `.dmg` build
- Email/calendar integrations
- Code-execution sandbox and richer goal tracking
