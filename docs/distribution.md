# Distribution Guide

## Packaging strategy

- The desktop app is bundled with Tauri.
- The Python backend is packaged as a standalone sidecar executable with PyInstaller.
- The sidecar is built into `/.build/nanobot-sidecar/dist/`.
- The desktop bundle copies the sidecar into an ignored staging directory at `apps/desktop/src-tauri/.sidecar/backend/` immediately before `tauri build`.
- The staging directory is cleaned after the bundle command finishes.
- On packaged startup, the Rust core process:
  - resolves OS-native app directories
  - creates data, logs, artifacts, and workspace directories
  - starts the backend sidecar
  - waits for the backend port to accept connections

## OS-native directories

The packaged app uses these logical directories:

- `APP_DATA_DIR`: SQLite and durable local state
- `APP_LOG_DIR`: backend log files
- `APP_ARTIFACTS_DIR`: generated artifacts and future exports
- `APP_WORKSPACE_ROOT`: default local workspace

On macOS these resolve under `~/Library/Application Support`, `~/Library/Logs`, and the user Documents directory.

On Windows these resolve under `%AppData%`, the app log directory chosen by Tauri, and the user Documents directory.

## Build flow

```bash
npm install

cd apps/backend
uv python install 3.11
uv sync
cd ../..

npm run dist
```

Standalone sidecar builds are also available with:

```bash
npm run build:backend:sidecar
```

## Current packaging limitations

- The packaged backend still binds to `127.0.0.1:8000`.
- There is no auto-updater or signing workflow yet.
- Windows and macOS notarization/signing are not configured in this phase.
- The sidecar packaging is built for the current host OS; cross-compilation is not configured.
- The repository no longer tracks a built sidecar binary.
