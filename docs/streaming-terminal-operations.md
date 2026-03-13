# Streaming and Terminal Operations

This branch integrates the async backend event stream, live chat run cards, and the `shell_exec` runtime.

## Run locally

Install dependencies and prepare the backend once:

```bash
npm install

cd apps/backend
uv python install 3.11
uv sync
npm run migrate
npm run seed
cd ../..
```

Start the backend only:

```bash
npm run dev:backend
```

Start the desktop UI only:

```bash
npm run dev:desktop
```

Start both together:

```bash
npm run dev
```

For browser-only frontend work, `npm run web:dev --workspace @nanobot/desktop` also works against the local backend.

## Health checks

Basic process health:

```bash
curl -s http://127.0.0.1:8000/health
```

Operational health, including the async execution worker:

```bash
curl -s http://127.0.0.1:8000/health/operational
```

Expected result:

- `status: "ok"` only when `scheduler`, `execution_worker`, and `subagent_worker` are all `running`
- `components.execution_worker` is present so async chat queue failures are visible to operators

## Test streaming manually

1. Create a session:

```bash
curl -s http://127.0.0.1:8000/sessions \
  -H 'content-type: application/json' \
  -d '{"title":"Streaming smoke"}'
```

2. Open the session event stream in a second terminal:

```bash
curl -N http://127.0.0.1:8000/sessions/<session_id>/events
```

3. Send an async message:

```bash
curl -s http://127.0.0.1:8000/sessions/<session_id>/messages/async \
  -H 'content-type: application/json' \
  -d '{"content":"List the main files in this workspace."}'
```

Expected session-stream sequence:

- replay of persisted history, if any
- `stream.ready`
- live events for the new run

Expected happy-path live sequence after `stream.ready`:

- `message.user.accepted`
- `assistant.run.created`
- `execution.started`
- zero or more tool events
- `message.completed`
- `execution.completed`

To validate replay protection, reconnect the second `curl` process with the last seen event id:

```bash
curl -N http://127.0.0.1:8000/sessions/<session_id>/events \
  -H 'Last-Event-ID: <event_id>'
```

Expected reconnect behavior:

- persisted events up to `<event_id>` are not delivered again
- the server may replay only newer persisted events
- the session stream emits `stream.ready` again after replay completes
- `stream.ready` itself has no `id`, so it does not affect replay or dedupe

## Test terminal manually

Allow the shell tool:

```bash
curl -s http://127.0.0.1:8000/tools/permissions/shell_exec \
  -X PUT \
  -H 'content-type: application/json' \
  -d '{"permission_level":"allow"}'
```

Run a simple command:

```bash
curl -s http://127.0.0.1:8000/sessions/<session_id>/messages/async \
  -H 'content-type: application/json' \
  -d '{"content":"tool:shell_exec command='\''pwd'\'' cwd=."}'
```

Expected stream behavior:

- `tool.started` includes `input_json` and `started_at`
- `tool.completed` includes `output_json`, `started_at`, and `finished_at`
- `message.completed` persists the assistant summary
- `execution.completed` closes the run

To validate timeout handling:

```bash
curl -s http://127.0.0.1:8000/sessions/<session_id>/messages/async \
  -H 'content-type: application/json' \
  -d '{"content":"tool:shell_exec command='\''sleep 2'\'' cwd=. timeout_seconds=1"}'
```

Expected terminal events:

- `tool.failed` with a timeout message
- `execution.failed` with the propagated error message

To validate approval flow, set `shell_exec` back to `ask` and trigger another shell message. The run should stop on `approval.requested`, and you can resolve it from the desktop Approvals inbox or the approvals API.

## Automated smoke coverage

Backend:

```bash
npm run test --workspace @nanobot/backend -- tests/test_execution_streaming.py tests/test_shell_tools.py
```

Desktop:

```bash
npm run test --workspace @nanobot/desktop -- \
  src/lib/backend/sessionExecutionStream.test.ts \
  src/hooks/controllers/chatExecutionState.test.ts \
  src/hooks/controllers/useChatController.test.tsx \
  src/components/AssistantRunCard.test.tsx \
  src/App.test.tsx
```

## Current limitations

- The stream is session-scoped and replays persisted events, not model token deltas.
- The session stream has two phases: replayed persisted history first, then live delivery after `stream.ready`.
- `shell_exec` returns summarized command results, not a persistent PTY or raw terminal stream.
- The execution worker and stream fan-out are process-local.
- Approval resolution is still inbox-driven; there is no inline approve/deny action inside the chat run card.
- The desktop keeps one live stream per active session and relies on `Last-Event-ID` plus event-id dedupe after reconnects.
