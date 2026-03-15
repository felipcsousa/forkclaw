use std::{
    fs::OpenOptions,
    net::TcpListener,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use serde::Serialize;
use tauri::{AppHandle, Manager, RunEvent, State};
use uuid::Uuid;

struct BackendProcess(Mutex<BackendProcessState>);

struct BackendProcessState {
    child: Option<Child>,
    port: Option<u16>,
    bootstrap_token: Option<String>,
    managed_by_shell: bool,
}

struct StartedBackend {
    child: Child,
    port: u16,
    bootstrap_token: String,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackendConnectionInfo {
    base_url: String,
    bootstrap_token: Option<String>,
    managed_by_shell: bool,
}

#[tauri::command]
fn get_backend_connection_info(state: State<'_, BackendProcess>) -> BackendConnectionInfo {
    let guard = state.0.lock().expect("backend mutex poisoned");
    let base_url = guard
        .port
        .map(|port| format!("http://127.0.0.1:{port}"))
        .unwrap_or_else(|| "http://127.0.0.1:8000".to_string());

    BackendConnectionInfo {
        base_url,
        bootstrap_token: guard.bootstrap_token.clone(),
        managed_by_shell: guard.managed_by_shell,
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_backend_connection_info])
        .setup(|app| {
            let should_spawn_sidecar = !cfg!(debug_assertions)
                || std::env::var("NANOBOT_FORCE_SIDECAR").ok().as_deref() == Some("1");

            if should_spawn_sidecar {
                let started = start_packaged_backend(app.handle())?;
                app.manage(BackendProcess(Mutex::new(BackendProcessState {
                    child: Some(started.child),
                    port: Some(started.port),
                    bootstrap_token: Some(started.bootstrap_token),
                    managed_by_shell: true,
                })));
            } else {
                app.manage(BackendProcess(Mutex::new(BackendProcessState {
                    child: None,
                    port: None,
                    bootstrap_token: None,
                    managed_by_shell: false,
                })));
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                let state = app.state::<BackendProcess>();
                let maybe_backend = {
                    let mut guard = state.0.lock().expect("backend mutex poisoned");
                    if !guard.managed_by_shell {
                        None
                    } else {
                        match (
                            guard.child.take(),
                            guard.port.take(),
                            guard.bootstrap_token.take(),
                        ) {
                            (Some(child), Some(port), Some(bootstrap_token)) => {
                                Some(StartedBackend {
                                    child,
                                    port,
                                    bootstrap_token,
                                })
                            }
                            _ => None,
                        }
                    }
                };
                if let Some(mut backend) = maybe_backend {
                    request_graceful_shutdown(backend.port, &backend.bootstrap_token);
                    if !wait_for_process_exit(&mut backend.child, Duration::from_secs(3)) {
                        let _ = backend.child.kill();
                        let _ = backend.child.wait();
                    }
                }
            }
        });
}

fn start_packaged_backend(app: &AppHandle) -> Result<StartedBackend, Box<dyn std::error::Error>> {
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

    let port = allocate_port()?;
    let bootstrap_token = Uuid::new_v4().to_string();
    let stdout_log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_dir.join("backend-stdout.log"))?;
    let stderr_log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_dir.join("backend-stderr.log"))?;
    let mut command = Command::new(backend_binary);
    let normalized_path = normalize_backend_path();
    command
        .env("APP_HOST", "127.0.0.1")
        .env("APP_PORT", port.to_string())
        .env("APP_BOOTSTRAP_TOKEN", &bootstrap_token)
        .env("APP_DATA_DIR", &data_dir)
        .env("APP_LOG_DIR", &log_dir)
        .env("APP_ARTIFACTS_DIR", &artifacts_dir)
        .env("APP_WORKSPACE_ROOT", &workspace_dir)
        .env("PATH", normalized_path)
        .stdout(Stdio::from(stdout_log))
        .stderr(Stdio::from(stderr_log));

    let mut child = command.spawn()?;
    if let Err(error) = wait_for_backend(port, &bootstrap_token) {
        let _ = child.kill();
        let _ = child.wait();
        return Err(error);
    }

    Ok(StartedBackend {
        child,
        port,
        bootstrap_token,
    })
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
        .join(".sidecar")
        .join("backend")
        .join(file_name))
}

fn allocate_port() -> Result<u16, Box<dyn std::error::Error>> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    let port = listener.local_addr()?.port();
    drop(listener);
    Ok(port)
}

fn wait_for_backend(port: u16, bootstrap_token: &str) -> Result<(), Box<dyn std::error::Error>> {
    let url = format!("http://127.0.0.1:{port}/health");
    let deadline = Instant::now() + Duration::from_secs(15);

    while Instant::now() < deadline {
        match ureq::get(&url)
            .set("X-Backend-Bootstrap-Token", bootstrap_token)
            .call()
        {
            Ok(response) => {
                let payload = response.into_string()?;
                if serde_json::from_str::<serde_json::Value>(&payload).is_ok() {
                    return Ok(());
                }
            }
            Err(_) => {}
        }
        thread::sleep(Duration::from_millis(250));
    }

    Err("Timed out waiting for the packaged backend to start.".into())
}

fn request_graceful_shutdown(port: u16, bootstrap_token: &str) {
    let url = format!("http://127.0.0.1:{port}/internal/shutdown");
    let _ = ureq::post(&url)
        .set("X-Backend-Bootstrap-Token", bootstrap_token)
        .call();
}

fn wait_for_process_exit(child: &mut Child, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        match child.try_wait() {
            Ok(Some(_)) => return true,
            Ok(None) => thread::sleep(Duration::from_millis(100)),
            Err(_) => return false,
        }
    }
    false
}

fn normalize_backend_path() -> std::ffi::OsString {
    let mut paths = std::env::var_os("PATH")
        .map(|value| std::env::split_paths(&value).collect::<Vec<PathBuf>>())
        .unwrap_or_default();
    for candidate in ["/opt/homebrew/bin", "/usr/local/bin"] {
        let path = PathBuf::from(candidate);
        if !paths.iter().any(|item| item == &path) {
            paths.push(path);
        }
    }
    std::env::join_paths(paths).unwrap_or_default()
}
