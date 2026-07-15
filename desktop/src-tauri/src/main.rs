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
// Wait up to 30s for the Python backend to come up before loading the UI —
// first launch can be slow (heartbeat scheduler, tool registration, imports).
const BACKEND_WAIT: Duration = Duration::from_secs(30);

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

fn backend_alive() -> bool {
    BACKEND_ADDR
        .parse()
        .ok()
        .and_then(|addr| {
            TcpStream::connect_timeout(&addr, Duration::from_millis(300)).ok()
        })
        .is_some()
}

fn configure_child(cmd: &mut Command) {
    // On Linux, ask the kernel to send the child SIGTERM if this process dies,
    // so a force-kill of the app never orphans the Python backend. (Normal
    // quit still kills it explicitly via kill_backend.)
    #[cfg(target_os = "linux")]
    {
        use std::os::unix::process::CommandExt;
        unsafe {
            cmd.pre_exec(|| {
                libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGTERM);
                Ok(())
            });
        }
    }
    let _ = cmd; // no-op on other platforms
}

fn spawn_backend() -> Option<Child> {
    // Reuse an already-running backend (e.g. one the user started manually, or
    // an orphan from a previous hard-kill) instead of spawning a duplicate
    // that would fail to bind port 8377. We return None so we don't later kill
    // a backend this instance didn't start.
    if backend_alive() {
        app_log("existing backend detected on :8377 — reusing it");
        return None;
    }

    // Prefer an explicit interpreter (packaged installs set REMY_PYTHON);
    // fall back to whatever python3/python is on PATH for dev runs.
    let candidates = [
        std::env::var("REMY_PYTHON").unwrap_or_default(),
        "python3".into(),
        "python".into(),
    ];
    for python in candidates.iter().filter(|c| !c.is_empty()) {
        let mut cmd = Command::new(python);
        cmd.args(["-m", "remy.api"]).current_dir(repo_root());
        configure_child(&mut cmd);
        match cmd.spawn() {
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

fn open_url(url: &str) {
    let _ = if cfg!(target_os = "macos") {
        Command::new("open").arg(url).spawn()
    } else if cfg!(target_os = "windows") {
        Command::new("cmd").args(["/C", "start", "", url]).spawn()
    } else {
        Command::new("xdg-open").arg(url).spawn()
    };
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
            // 1. backend: spawn it. The window loads the BUNDLED React UI
            //    instantly (local assets, no network) so there's never a
            //    "can't reach this page" flash; the UI polls the backend's
            //    /health itself and shows Connecting → Online as it comes up.
            let backend = spawn_backend();
            *app.state::<Backend>().0.lock().unwrap() = backend;
            std::thread::spawn(|| {
                // Log readiness for diagnostics; the UI handles the UX.
                if wait_for_backend() {
                    app_log("backend healthy");
                } else {
                    app_log("WARNING: backend not healthy within 30s");
                }
            });

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
                        // Settings = the advanced HUD dashboard (personality
                        // dials, audit, approvals), opened in the browser so
                        // the app window stays on the chat UI.
                        open_url("http://localhost:8377/hud");
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
