# Chat Live Runs UI States

This desktop worktree renders assistant execution as live run cards grouped by `task_run_id`.

## States

- `running`: The assistant accepted the task and is still executing steps. Tool rows can move from requested to completed or failed while the card stays open.
- `awaiting_approval`: The run is paused on a tool approval. The card stays inline in chat and keeps the existing step history visible.
- `failed`: The run ended with an execution or tool failure. The card keeps the failure state and preserves step history for inspection.
- `completed`: The final assistant message is available. The card consolidates into the assistant response and keeps steps behind expandable details.
- `disconnected` / `reconnecting`: The SSE stream is not healthy. The card shows a live-updates warning and the desktop falls back to periodic session refresh while active runs remain open.

## Step Types

- Tool execution: Compact row with tool name, status, duration, and a short argument/result summary.
- Shell execution: Rendered as a normal tool step. Stdout/stderr stay hidden by default and only appear in expandable details.
- Approval: Inline approval-needed state within the active run.
- Subagent: Inline step that signals child-session work while keeping the existing child-session cards and sheet intact.

## Finalization Rules

- Runs are grouped by `task_run_id`, not `message_id`.
- The persisted assistant message is hidden from the standard message list when the live run card already renders that same final message.
- Existing message history and subagent views remain available during the migration.
