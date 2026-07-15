# REMY v1.1.0 — Autonomous Desktop AI Agent

## ✨ What's New — Streaming responses

- **Token-by-token streaming** — REMY's replies now stream in as they're
  generated instead of appearing all at once, with an animated cursor (▌)
  showing while a response is in progress. Feels instant, and you can start
  reading before REMY finishes thinking.
- Streaming works through REMY's full tool loop — file reads, shell
  commands, browser automation, and sub-agent delegation all still run
  exactly as before; only the final text is streamed.
- If a connection drops mid-reply, REMY appends a clear inline error instead
  of leaving you with a stuck spinner.

## ✨ From v1.0.2 — UI/UX polish

- Welcome empty-state with one-click suggestion cards.
- Copy buttons on messages and code blocks, with hover timestamps.
- Light/dark theme that follows your OS, with a header toggle.
- Polished input bar: focus ring, character counter, gradient send button.
- Message grouping and refreshed spacing for readability.

## ✨ From v1.0.1

- Bundled React chat UI served by the local backend; advanced HUD dashboard
  at `/hud`.
- Autonomous heartbeat, self-pruning tiered memory, multi-agent
  orchestration, browser automation, permission-gated desktop control, full
  audit logging, optional voice.

## 📥 Install

| Platform | Steps |
|---|---|
| **Windows** | Download `remy-*-windows-*.msi` → double-click → Install → launch from the Start menu |
| **macOS** (Apple Silicon) | Download `remy-*-macos-*.dmg` → drag REMY to Applications → launch |
| **Linux** | Download `remy-*-linux-*.AppImage` → `chmod +x` → run (or install the `.deb`) |

Verify downloads against `SHA256SUMS.txt`.

## ⚙️ One-time backend setup (required)

The installers ship the desktop shell + chat UI; REMY's brain is a Python
service the app starts for you. It needs **Python ≥ 3.11** once:

```bash
pip install "remy[llm,memory,desktop,browser] @ git+https://github.com/hirthik-shanmugam/remy-.git"
```

Add your `ANTHROPIC_API_KEY` to `.env` to bring the reasoning engine online.
Without a key, REMY still runs the chat shell, HUD, permission layer, and
rule-based heartbeat — replies stream even in this offline mode.

## 🚀 First run

1. Launch REMY — the chat window opens immediately (Connecting → Online).
2. Pick a suggestion card or type your own message; watch the reply stream in.
3. The same chat is at `http://localhost:8377`; the advanced HUD is at
   `http://localhost:8377/hud` (tray → **Settings**).

## 📝 Notes

- **Unsigned builds**: Windows SmartScreen → "More info → Run anyway";
  macOS → right-click → Open.
- **Tray**: closing the window keeps REMY running; **Quit** stops the app and
  the backend.
- **Local-only**: everything binds to localhost; only LLM calls leave your
  machine.

## 🎯 Next

- Bundled Python runtime (true zero-setup install)
- Intel-mac `.dmg`, email/calendar integrations
