# REMY Desktop Shell (Tauri)

Cross-platform (Windows + macOS, Linux too) always-on shell around the REMY
backend. It spawns `python -m remy.api` (dashboard + heartbeat + permission
layer), shows the HUD window, and lives in the system tray — closing the
window hides it while REMY's heartbeat keeps running. Quit from the tray menu.

## Prerequisites

- Rust toolchain (`rustup`), plus platform Tauri deps:
  https://v2.tauri.app/start/prerequisites/
- Python ≥ 3.11 with REMY installed in the repo root:
  `pip install -e ".[llm,memory,desktop]"`

## Dev run

```bash
cd desktop/src-tauri
cargo tauri dev        # or: cargo run
```

The shell looks for `python3`/`python` on PATH (override with `REMY_PYTHON`)
and the repo root two levels up (override with `REMY_ROOT`).

## Release bundles

```bash
cd desktop/src-tauri
cargo tauri build      # .msi/.nsis on Windows, .dmg/.app on macOS
```

Note: for a fully self-contained installer, ship a Python environment as a
Tauri sidecar and point `REMY_PYTHON` at it; by default the app expects a
system Python with REMY installed.
