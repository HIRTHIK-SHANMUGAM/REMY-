// REMY desktop shell — Tauri v2
//
// Responsibilities:
//   1. Spawn the Python backend (`python -m remy.api`: FastAPI + heartbeat +
//      permission layer) and wait up to ~5s for it to listen on :8377.
//   2. Show the HUD window pointed at http://localhost:8377/.
//   3. Live in the system tray: [Open, Settings, Quit]. Closing the window
//      hides it; REMY (and its heartbeat) keeps running until Quit.
//   4. Kill the Python child on quit. Log lifecycle events to
//      remy_data/app.log.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::Write;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, WindowEvent,
};

const BACKEND_ADDR: &str = "127.0.0.1:8377";
const BACKEND_WAIT: Duration = Duration::from_secs(5);

struct Backend(Mutex<Option<Child>>);

fn repo_root() -> PathBuf {
    std::env::var("REMY_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("../.."))
}

fn app_log(message: &str) {
    let log_dir = repo_root().join("remy_data");
    let _ = std::fs::create_dir_all(&log_dir);
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_dir.join("app.log"))
    {
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let _ = writeln!(f, "[{ts}] {message}");
    }
}

fn spawn_backend() -> Option<Child> {
    // Prefer an explicit interpreter (packaged installs set REMY_PYTHON);
    // fall back to whatever python3/python is on PATH for dev runs.
    let candidates = [
        std::env::var("REMY_PYTHON").unwrap_or_default(),
        "python3".into(),
        "python".into(),
    ];
    for python in candidates.iter().filter(|c| !c.is_empty()) {
        match Command::new(python)
            .args(["-m", "remy.api"])
            .current_dir(repo_root())
            .spawn()
        {
            Ok(child) => {
                app_log(&format!("backend spawned via {python} (pid {})", child.id()));
                return Some(child);
            }
            Err(_) => continue,
        }
    }
    app_log("ERROR: no python interpreter found; backend not started");
    None
}

fn wait_for_backend() -> bool {
    let deadline = Instant::now() + BACKEND_WAIT;
    while Instant::now() < deadline {
        if TcpStream::connect_timeout(&BACKEND_ADDR.parse().unwrap(),
                                      Duration::from_millis(300))
            .is_ok()
        {
            app_log("backend is listening on 127.0.0.1:8377");
            return true;
        }
        std::thread::sleep(Duration::from_millis(250));
    }
    app_log("WARNING: backend not reachable after 5s; window will retry");
    false
}

fn kill_backend(app: &tauri::AppHandle) {
    if let Some(mut child) = app.state::<Backend>().0.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
        app_log("backend killed on quit");
    }
}

fn main() {
    app_log("REMY desktop starting");
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            // 1. backend: spawn, then wait up to 5s for :8377
            let backend = spawn_backend();
            *app.state::<Backend>().0.lock().unwrap() = backend;
            wait_for_backend();
            if let Some(w) = app.get_webview_window("main") {
                // (re)load now that the backend is up
                let _ = w.eval("window.location.replace('http://localhost:8377/')");
            }

            // 2. tray: [Open, Settings, Quit]
            let open = MenuItem::with_id(app, "open", "Open", true, None::<&str>)?;
            let settings =
                MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &settings, &quit])?;

            TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("REMY — autonomous agent")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "settings" => {
                        // Settings = the dashboard's personality/settings panels
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.eval(
                                "window.location.replace('http://localhost:8377/?panel=settings')");
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "quit" => {
                        app_log("quit requested from tray");
                        kill_backend(app);
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;
            app_log("window + tray ready");
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
        .build(tauri::generate_context!())
        .expect("error while building REMY")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                kill_backend(app);
                app_log("REMY desktop exited");
            }
        });
}
