# REMY v1.0.2 — Autonomous Desktop AI Agent

## ✨ What's New — UI/UX polish

This release is a focused refresh of the chat interface.

- **Welcome empty-state** — the app now opens to an inviting welcome screen
  with four one-click suggestion cards (summarize a file, check system health,
  schedule a task, "what can you do?") instead of a bare greeting. Pick one to
  start instantly.
- **Copy buttons** — hover any REMY message for a copy button and a timestamp;
  fenced code blocks get their own copy button so you can grab snippets in one
  click.
- **Light & dark mode** — REMY now follows your OS theme automatically, with a
  sun/moon toggle in the header to override it. Your choice is remembered, and
  there's no flash on launch.
- **Improved input bar** — a stronger focus ring, a gradient send button with
  tactile press feedback, a character counter for long messages, and a hint
  that stays out of the way until you're typing.
- **Better spacing & readability** — consecutive messages from REMY now group
  under a single avatar, bubbles use a subtle gradient and depth, and muted
  text was brightened for accessible contrast in both themes.

## ✨ Everything from v1.0.1

- Bundled React chat UI served by the local backend; advanced HUD dashboard at
  `/hud`.
- Autonomous heartbeat, self-pruning tiered memory, multi-agent orchestration,
  browser automation, permission-gated desktop control, full audit logging,
  optional voice.

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
rule-based heartbeat.

## 🚀 First run

1. Launch REMY — the chat window opens immediately (Connecting → Online).
2. Pick a suggestion card or type your own message.
3. The same chat is at `http://localhost:8377`; the advanced HUD is at
   `http://localhost:8377/hud` (tray → **Settings**).

## 📝 Notes

- **Unsigned builds**: Windows SmartScreen → "More info → Run anyway";
  macOS → right-click → Open.
- **Tray**: closing the window keeps REMY running; **Quit** stops the app and
  the backend.
- **Local-only**: everything binds to localhost; only LLM calls leave your
  machine.

## 🎯 Next (v1.1+)

- Streaming responses (token-by-token replies)
- Bundled Python runtime (true zero-setup install)
- Intel-mac `.dmg`, email/calendar integrations
