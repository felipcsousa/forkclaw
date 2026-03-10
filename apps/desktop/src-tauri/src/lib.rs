use std::{
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use tauri::{AppHandle, Manager, RunEvent};

struct BackendProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let should_spawn_sidecar = !cfg!(debug_assertions)
                || std::env::var("NANOBOT_FORCE_SIDECAR").ok().as_deref() == Some("1");

            if should_spawn_sidecar {
                let child = start_packaged_backend(app.handle())?;
                app.manage(BackendProcess(Mutex::new(Some(child))));
            } else {
                app.manage(BackendProcess(Mutex::new(None)));
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                let state = app.state::<BackendProcess>();
                let maybe_child = {
                    let mut guard = state.0.lock().expect("backend mutex poisoned");
                    guard.take()
                };
                if let Some(mut child) = maybe_child {
                    let _ = child.kill();
                }
            }
        });
}

fn start_packaged_backend(app: &AppHandle) -> Result<Child, Box<dyn std::error::Error>> {
    let backend_binary = resolve_backend_binary(app)?;
    let data_dir = app.path().app_data_dir()?;
    let log_dir = app
        .path()
        .app_log_dir()
        .unwrap_or_else(|_| data_dir.join("logs"));
    let artifacts_dir = data_dir.join("artifacts");
    let workspace_dir = app
        .path()
        .document_dir()
        .unwrap_or_else(|_| data_dir.clone())
        .join("Nanobot Agent Workspace");

    std::fs::create_dir_all(&data_dir)?;
    std::fs::create_dir_all(&log_dir)?;
    std::fs::create_dir_all(&artifacts_dir)?;
    std::fs::create_dir_all(&workspace_dir)?;

    let port = "8000";
    let mut command = Command::new(backend_binary);
    command
        .env("APP_HOST", "127.0.0.1")
        .env("APP_PORT", port)
        .env("APP_DATA_DIR", &data_dir)
        .env("APP_LOG_DIR", &log_dir)
        .env("APP_ARTIFACTS_DIR", &artifacts_dir)
        .env("APP_WORKSPACE_ROOT", &workspace_dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    let child = command.spawn()?;
    wait_for_backend(port.parse()?)?;
    Ok(child)
}

fn resolve_backend_binary(app: &AppHandle) -> Result<PathBuf, Box<dyn std::error::Error>> {
    let file_name = if cfg!(target_os = "windows") {
        "nanobot-agent-backend.exe"
    } else {
        "nanobot-agent-backend"
    };
    Ok(app
        .path()
        .resource_dir()?
        .join("resources")
        .join("backend")
        .join(file_name))
}

fn wait_for_backend(port: u16) -> Result<(), Box<dyn std::error::Error>> {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let deadline = Instant::now() + Duration::from_secs(15);

    while Instant::now() < deadline {
        if TcpStream::connect_timeout(&address, Duration::from_millis(250)).is_ok() {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(250));
    }

    Err("Timed out waiting for the packaged backend to start.".into())
}
