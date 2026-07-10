# REMY — Autonomous Desktop AI Agent

Local-first JARVIS-style agent: persistent memory, adjustable personality,
permission-gated desktop control, self-directed heartbeat, browser automation,
and a polished chat UI — running entirely on your machine.

**New in v1.0.1:** a bundled React chat interface. The desktop app opens
straight into the chat window (the advanced HUD dashboard is one click away
under the tray's **Settings**).

## Install

**Download, double-click, run.**

| Platform | File |
|---|---|
| Windows 10/11 | `remy-*-windows-*.msi` (or the `-setup.exe`) |
| macOS 12+ (Intel & Apple Silicon) | `remy-*-macos-*.dmg` — drag REMY to Applications |
| Linux | `remy-*-linux-*.AppImage` (chmod +x) or the `.deb` |

Verify your download (optional): compare against `SHA256SUMS.txt`.

## One-time backend setup

REMY's brain is a Python service the app starts for you. It needs Python ≥ 3.11
on your machine (python.org or `winget install Python.Python.3.12` /
`brew install python`):

```bash
pip install remy[llm,memory,desktop,browser] @ git+https://github.com/hirthik-shanmugam/remy-.git
```

Then launch REMY from your apps menu. On first run, open **Settings** (tray
menu) and add your `ANTHROPIC_API_KEY` to bring the reasoning engine online —
without it REMY still runs the dashboard, permission layer, and rule-based
heartbeat.

## Notes

- **Unsigned builds**: Windows SmartScreen → "More info → Run anyway";
  macOS → right-click → Open (or System Settings → Privacy → Open Anyway).
- REMY lives in your system tray. Closing the window keeps it running;
  choose **Quit** from the tray icon to stop it (this also stops the backend).
- Everything binds to `localhost` only. Logs: `remy_data/app.log`,
  full audit trail on the dashboard.

## Feature summary

- **Autonomy**: heartbeat loop wakes REMY on an interval; standing orders
  (condition → action → escalation) decide what needs doing; every action is
  audit-logged, and anything risky waits for your approval.
- **Permission layer enforced in code**: three risk tiers, hard denylist for
  destructive commands, filesystem allowlist, blocking approval queue.
- **Memory**: tiered self-pruning store — hot episodic log, decay-scored
  semantic facts, compressed archive; pinned facts never decay.
- **Personality**: humour, warmth, seriousness, sarcasm, formality, verbosity,
  proactivity, empathy — each an adjustable 0–100% dial.
- **Desktop + web control**: files, shell, apps, screen, input automation
  (per-action approval), and Playwright browser automation with auth/financial
  site protection.
- **Voice** (optional): LiveKit STT/TTS pipeline.
