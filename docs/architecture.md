# Technical Architecture

## Product layers

### 1. Agent Console

- Tauri desktop shell
- React + TypeScript UI
- Talks only to the local backend over HTTP

### 2. Agent OS

- FastAPI application
- SQLite source of truth
- Scheduler, approvals, tasks, audit trail, settings, and tool policies

### 3. Agent Kernel boundary

- Internal contracts live under `app/kernel`
- Product code talks to `AgentKernelPort`
- Nanobot is behind `app/adapters/kernel/nanobot.py`

### 4. Distribution layer

- Tauri bundles the desktop app
- Python backend is packaged as a sidecar executable
- OS-native app data directories store SQLite, logs, and artifacts

## Canonical state

- SQLite is the canonical state store for product data
- Keychain stores provider API keys and other sensitive secrets
- Markdown is optional editorial projection only and is not used as a source of truth

## Main runtime flows

### Chat execution

1. The desktop posts a message to `/sessions/{id}/messages`
2. The backend persists the user message, task, and task run
3. `AgentExecutionService` builds a kernel request from SQLite state
4. The Nanobot adapter runs the provider flow
5. Assistant output, tool calls, approvals, and audit events are persisted

### Tool authorization

1. The kernel requests a tool
2. `ToolService` loads the tool policy from SQLite
3. The call is marked `deny`, `ask`, or `allow`
4. Tool calls and related audit events are always persisted

### Approval flow

1. `ask` creates an approval row and pauses the execution
2. The desktop inbox reads `/approvals`
3. Approve or deny actions resume or fail the pending execution

### Scheduler and heartbeat

1. Cron jobs are stored in SQLite
2. The local scheduler polls due jobs
3. Each run creates `task_runs` and audit history
4. Heartbeat performs operational maintenance and records real activity

## Data layout

Core tables:

- `agents`, `agent_profiles`
- `sessions`, `messages`
- `tasks`, `task_runs`
- `tool_permissions`, `tool_calls`
- `approvals`
- `cron_jobs`
- `audit_events`
- `settings`

## Observability model

- `audit_events` are the low-level audit trail
- `/activity/timeline` is the aggregated product-facing execution trace
- backend request logging adds `X-Request-ID` for support correlation

## Distribution model

- Dev mode runs backend and desktop separately
- Packaged mode starts the backend sidecar from the Tauri core process
- The sidecar applies migrations on startup and writes into OS-native directories

## Key extension points

- Swap kernel implementations behind `AgentKernelPort`
- Add richer tool sandboxing without changing UI contracts
- Move from fixed backend port to negotiated runtime port
- Add signed updates and release automation on top of the current bundle flow
