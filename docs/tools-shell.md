# Shell tool runtime

## `shell_exec`

Request payload:

```json
{
  "command": "pwd",
  "cwd": ".",
  "timeout_seconds": 15,
  "env": {
    "PATH": "/usr/bin:/bin"
  }
}
```

Response payload:

```json
{
  "stdout": "/workspace\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 12,
  "cwd_resolved": "/workspace",
  "truncated": false
}
```

Example agent call:

```text
tool:shell_exec command='pwd' cwd=.
```

## Safety limits

- Permission default stays `ask` because `shell_exec` is a high-risk runtime tool.
- `cwd` may resolve only inside the configured workspace or inside `runtime.shell_exec_allowed_cwd_roots`.
- Absolute `cwd` values outside the allowlist fail before execution.
- Environment overrides are restricted to `runtime.shell_exec_allowed_env_keys`.
- Timeout defaults to `TOOL_TIMEOUT_SECONDS` and is clamped by `runtime.shell_exec_max_timeout_seconds`.
- `stdout` and `stderr` are truncated independently using `runtime.shell_exec_max_output_chars`.
- The backend emits audit/timeline events `tool.started`, `tool.completed`, and `tool.failed`.

## Known risks

- This is still local command execution, so approval and allowlists reduce risk but do not eliminate it.
- Commands are stateless per call. There is no session reuse, PTY, or process persistence yet.
- The tool intentionally returns execution results in chat-facing summaries and structured payloads, not raw terminal streaming.

## Stateful shell follow-up

- The implementation now has a shell-specific runtime boundary and preview flow that can be extended with `session_id`.
- A future PTY/session version should add explicit process lifecycle management, idle cleanup, and stronger isolation for long-lived shells.
- No terminal UI should be added; session state should continue to surface as tool events and summarized results.
