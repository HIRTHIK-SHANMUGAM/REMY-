// REMY desktop shell — Tauri v2
//
// Responsibilities:
//   1. Spawn the Python backend (remy.api: FastAPI + heartbeat + MCP tools)
//      as a child process, and keep it alive while the app runs.
//   2. Show the HUD window pointed at http://127.0.0.1:8377/.
//   3. Live in the system tray: closing the window hides it, REMY (and its
//      heartbeat) keeps running until the user picks Quit from the tray.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, WindowEvent,
};

struct Backend(Mutex<Option<Child>>);

fn spawn_backend() -> Option<Child> {
    // Prefer an explicit interpreter (packaged installs set REMY_PYTHON);
    // fall back to whatever python3/python is on PATH for dev runs.
    let candidates = [
        std::env::var("REMY_PYTHON").unwrap_or_default(),
        "python3".into(),
        "python".into(),
    ];
    for python in candidates.iter().filter(|c| !c.is_empty()) {
        let child = Command::new(python)
            .args(["-m", "remy.api"])
            // repo root = two levels up from desktop/src-tauri in dev
            .current_dir(
                std::env::var("REMY_ROOT").unwrap_or_else(|_| "../..".into()),
            )
            .spawn();
        if let Ok(c) = child {
            return Some(c);
        }
    }
    eprintln!("REMY backend could not be started: no python found");
    None
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            // 1. backend
            let backend = spawn_backend();
            *app.state::<Backend>().0.lock().unwrap() = backend;

            // 2. tray
            let show = MenuItem::with_id(app, "show", "Show REMY", true, None::<&str>)?;
            let heartbeat =
                MenuItem::with_id(app, "heartbeat", "Run heartbeat now", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit REMY", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &heartbeat, &quit])?;

            TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("REMY — autonomous agent")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "heartbeat" => {
                        // fire-and-forget; the dashboard reflects the result
                        std::thread::spawn(|| {
                            let _ = std::process::Command::new("curl")
                                .args([
                                    "-s",
                                    "-X",
                                    "POST",
                                    "http://127.0.0.1:8377/api/heartbeat/run",
                                ])
                                .output();
                        });
                    }
                    "quit" => {
                        if let Some(mut child) =
                            app.state::<Backend>().0.lock().unwrap().take()
                        {
                            let _ = child.kill();
                        }
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        // Closing the window hides it — REMY stays alive in the tray so the
        // heartbeat keeps running (always-on background app).
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running REMY");
}
