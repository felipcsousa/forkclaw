# Backend Execution Events

## Endpoints

- `POST /sessions/{session_id}/messages/async`
  - Starts an async execution and returns `202 Accepted`.
  - Response fields: `session_id`, `task_id`, `task_run_id`, `user_message_id`, `status`, `events_url`.
- `GET /sessions/{session_id}/events`
  - Streams execution events as Server-Sent Events.
  - Optional query param: `task_run_id`.
  - Optional header: `Last-Event-ID`.

## SSE Format

Each event is sent as:

```text
id: <stable-event-id>
event: <event-type>
data: <json-envelope>
```

The JSON envelope has this shape:

```json
{
  "id": "audit:123",
  "type": "execution.completed",
  "created_at": "2026-03-12T19:24:42.123456Z",
  "session_id": "session-id",
  "task_id": "task-id",
  "task_run_id": "task-run-id",
  "data": {}
}
```

## Event Types

- `message.user.accepted`: user message was persisted and linked to an async run.
- `assistant.run.created`: async task/task run was created and queued.
- `execution.started`: worker claimed the run and started kernel execution.
- `tool.started`: a tool call record was created for the run.
- `tool.completed`: the tool finished successfully.
- `tool.failed`: the tool finished with error.
- `approval.requested`: execution paused waiting for user approval.
- `subagent.spawned`: a child subagent session was created from this session.
- `message.completed`: the final assistant message was persisted.
- `execution.completed`: the task run finished successfully.
- `execution.failed`: the task run finished with failure.

## Notes

- The stream uses persisted backend state as the source of truth. It does not emit token deltas.
- The `data` payload varies by event type and includes the minimum identifiers needed by the frontend, such as `message`, `tool_call_id`, `tool_name`, `approval_id`, and `status`.
- `tool.started`, `tool.completed`, and `tool.failed` now include persisted `input_json`, `output_json` when available, plus `started_at` and `finished_at` for timeline duration math.
- `execution.started`, `execution.completed`, and `execution.failed` include `started_at`, `finished_at`, and `error_message` when the backend has a persisted failure reason.
- When `task_run_id` is provided, the backend closes the SSE response after `approval.requested`, `execution.completed`, or `execution.failed` so task-specific consumers can treat the stream as finite.
- The current worker is process-local. In a multi-instance deployment, queue claiming and stream fan-out need extra coordination.
