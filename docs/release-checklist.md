# Release Checklist

## Before packaging

- Verify `npm run lint`
- Verify `npm run test`
- Verify `npm run build --workspace @nanobot/desktop`
- Verify `npm run build:backend:sidecar`

## Packaging

- Run `npm run dist`
- Confirm a Tauri bundle is generated for the current OS
- Confirm no sidecar artifacts appear in `git status`
- Launch the packaged app locally
- Confirm `agent_os.db` is created in the OS app data directory
- Confirm `backend.log` is created in the OS log directory
- Confirm the backend responds to `GET /health`

## Manual smoke checks

- Create a session
- Send a message
- Open the Settings view
- Confirm workspace root and budgets persist
- Confirm tool approvals still work

## Known follow-ups before public release

- Add code signing for macOS and Windows
- Add updater strategy and rollback plan
- Move backend port selection away from a fixed default
- Add installer QA for first-run migrations and keychain access
