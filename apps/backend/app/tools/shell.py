from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.tools.base import ToolDescriptor, ToolExecutionContext, ToolResult


class ShellExecPermissionError(PermissionError):
    def __init__(self, message: str, *, audit_payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.audit_payload = audit_payload or {}


class ShellExecTimeoutError(TimeoutError):
    def __init__(self, message: str, *, audit_payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.audit_payload = audit_payload or {}


class ShellExecRuntimeError(RuntimeError):
    def __init__(self, message: str, *, audit_payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.audit_payload = audit_payload or {}


@dataclass(frozen=True)
class ShellExecutionPreview:
    command: str
    cwd_resolved: str
    cwd_policy: str
    env_keys: list[str]
    timeout_seconds: float
    session_id: str | None = None


@dataclass(frozen=True)
class ShellSessionState:
    session_id: str | None = None
    cwd_resolved: str | None = None


class ShellExecTool:
    descriptor = ToolDescriptor(
        name="shell_exec",
        label="Shell exec",
        description=(
            "Execute a local shell command inside the workspace or an allowlisted host path."
        ),
        group="group:runtime",
        risk="high",
        status="experimental",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
                "cwd": {
                    "type": "string",
                    "description": (
                        "Working directory, relative to the workspace or absolute in the "
                        "allowlist."
                    ),
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Optional timeout in seconds for this command.",
                    "minimum": 1,
                    "maximum": 600,
                },
                "env": {
                    "type": "object",
                    "description": (
                        "Optional environment variable overrides restricted by allowlist."
                    ),
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "exit_code": {"type": ["integer", "null"]},
                "duration_ms": {"type": "integer"},
                "cwd_resolved": {"type": "string"},
                "truncated": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        requires_workspace=True,
    )

    def preview(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ShellExecutionPreview:
        config = _ShellExecConfig.from_runtime_settings(context.runtime_settings)
        command = _require_command(arguments.get("command"))
        requested_env = _read_env_map(arguments.get("env"))
        cwd_resolved, cwd_policy = _resolve_cwd(
            workspace_root=context.workspace_root,
            requested_cwd=arguments.get("cwd"),
            allowed_roots=config.allowed_cwd_roots,
        )
        timeout_seconds = _resolve_timeout(
            arguments.get("timeout_seconds"),
            default_seconds=config.default_timeout_seconds,
            max_seconds=config.max_timeout_seconds,
        )
        _build_allowed_env(
            requested_env=requested_env,
            allowed_env_keys=config.allowed_env_keys,
        )
        return ShellExecutionPreview(
            command=command,
            cwd_resolved=str(cwd_resolved),
            cwd_policy=cwd_policy,
            env_keys=sorted(requested_env),
            timeout_seconds=timeout_seconds,
        )

    def requested_action(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> str:
        preview = self.preview(context=context, arguments=arguments)
        env_keys = ", ".join(preview.env_keys) if preview.env_keys else "(none)"
        timeout_text = int(preview.timeout_seconds)
        return (
            f"shell_exec(command={preview.command!r}, cwd={preview.cwd_resolved}, "
            f"cwd_policy={preview.cwd_policy}, timeout_seconds={timeout_text}, env_keys={env_keys})"
        )

    def execute(
        self,
        *,
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        preview = self.preview(context=context, arguments=arguments)
        config = _ShellExecConfig.from_runtime_settings(context.runtime_settings)
        requested_env = _read_env_map(arguments.get("env"))
        env = _build_allowed_env(
            requested_env=requested_env,
            allowed_env_keys=config.allowed_env_keys,
        )

        shell_binary = shutil.which("bash") or shutil.which("sh")
        if shell_binary is None:
            raise ShellExecRuntimeError("No supported shell binary (`bash` or `sh`) is available.")

        started_at = time.perf_counter()
        try:
            command = [shell_binary, "-c", preview.command]
            if "bash" in Path(shell_binary).name:
                command = [shell_binary, "--noprofile", "--norc", "-c", preview.command]
            completed = subprocess.run(
                command,
                cwd=preview.cwd_resolved,
                env=env,
                capture_output=True,
                text=True,
                timeout=preview.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            raise ShellExecTimeoutError(
                f"Command timed out after {int(preview.timeout_seconds)} seconds.",
                audit_payload={
                    "cwd_resolved": preview.cwd_resolved,
                    "duration_ms": duration_ms,
                },
            ) from exc
        except OSError as exc:
            raise ShellExecRuntimeError(
                f"Shell execution failed to start: {exc}",
                audit_payload={"cwd_resolved": preview.cwd_resolved},
            ) from exc

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        stdout, stdout_truncated = _truncate_output(completed.stdout, config.max_output_chars)
        stderr, stderr_truncated = _truncate_output(completed.stderr, config.max_output_chars)
        payload = {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": completed.returncode,
            "duration_ms": duration_ms,
            "cwd_resolved": preview.cwd_resolved,
            "truncated": stdout_truncated or stderr_truncated,
        }
        return ToolResult(
            output_text=_format_shell_summary(payload),
            output_data=payload,
        )


@dataclass(frozen=True)
class _ShellExecConfig:
    default_timeout_seconds: float
    max_timeout_seconds: float
    max_output_chars: int
    allowed_cwd_roots: tuple[Path, ...]
    allowed_env_keys: frozenset[str]

    @classmethod
    def from_runtime_settings(cls, runtime_settings: dict[str, Any] | Any) -> _ShellExecConfig:
        raw_allowed_roots = runtime_settings.get("shell_exec_allowed_cwd_roots", [])
        raw_allowed_env = runtime_settings.get("shell_exec_allowed_env_keys", ["PATH"])
        return cls(
            default_timeout_seconds=float(runtime_settings.get("tool_timeout_seconds", 15.0)),
            max_timeout_seconds=max(
                float(runtime_settings.get("shell_exec_max_timeout_seconds", 60.0)),
                1.0,
            ),
            max_output_chars=max(
                int(runtime_settings.get("shell_exec_max_output_chars", 12000)),
                32,
            ),
            allowed_cwd_roots=tuple(_normalize_path_list(raw_allowed_roots)),
            allowed_env_keys=frozenset(_normalize_string_list(raw_allowed_env)),
        )


def _require_command(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing required string argument: command")
    return value.strip()


def _read_env_map(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Invalid object argument: env")

    parsed: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Environment variable names must be non-empty strings.")
        if not isinstance(item, str):
            raise ValueError(f"Environment variable `{key}` must have a string value.")
        parsed[key] = item
    return parsed


def _normalize_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if cleaned:
                items.append(cleaned)
        return items
    return []


def _normalize_path_list(value: object) -> list[Path]:
    items = _normalize_string_list(value)
    return [Path(item).expanduser().resolve() for item in items]


def _resolve_cwd(
    *,
    workspace_root: Path,
    requested_cwd: object,
    allowed_roots: tuple[Path, ...],
) -> tuple[Path, str]:
    raw_value = "."
    if requested_cwd is not None:
        if not isinstance(requested_cwd, str) or not requested_cwd.strip():
            raise ValueError("cwd must be a non-empty string when provided.")
        raw_value = requested_cwd.strip()

    raw_path = Path(raw_value)
    if raw_path.is_absolute():
        resolved = raw_path.expanduser().resolve()
    else:
        resolved = (workspace_root / raw_path).resolve()

    workspace_root = workspace_root.resolve()
    if resolved == workspace_root or resolved.is_relative_to(workspace_root):
        policy = "workspace"
    elif any(resolved == root or resolved.is_relative_to(root) for root in allowed_roots):
        policy = "allowlist"
    else:
        raise ShellExecPermissionError(
            "Shell cwd must stay inside the workspace or a configured allowlist root.",
            audit_payload={"cwd_resolved": str(resolved)},
        )

    if not resolved.exists():
        raise FileNotFoundError(f"Shell cwd does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Shell cwd is not a directory: {resolved}")
    return resolved, policy


def _resolve_timeout(value: object, *, default_seconds: float, max_seconds: float) -> float:
    if value is None:
        parsed = default_seconds
    else:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid numeric argument: timeout_seconds") from exc
    return max(1.0, min(parsed, max_seconds))


def _build_allowed_env(
    *,
    requested_env: dict[str, str],
    allowed_env_keys: frozenset[str],
) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in allowed_env_keys:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value

    for key, value in requested_env.items():
        if key not in allowed_env_keys:
            raise ShellExecPermissionError(
                f"Environment variable `{key}` is not in the configured allowlist.",
                audit_payload={"env_key": key},
            )
        env[key] = value
    return env


def _truncate_output(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    suffix = "\n...[truncated]"
    budget = max(max_chars - len(suffix), 0)
    return f"{value[:budget]}{suffix}", True


def _format_shell_summary(payload: dict[str, Any]) -> str:
    lines = [
        (
            f"Shell command finished with exit code {payload['exit_code']} "
            f"in {payload['duration_ms']} ms."
        ),
        f"cwd: {payload['cwd_resolved']}",
    ]
    stdout = str(payload.get("stdout") or "")
    stderr = str(payload.get("stderr") or "")
    if stdout:
        lines.append("stdout:")
        lines.append(stdout.rstrip("\n"))
    if stderr:
        lines.append("stderr:")
        lines.append(stderr.rstrip("\n"))
    if payload.get("truncated"):
        lines.append("Output was truncated to fit the tool limit.")
    return "\n".join(lines).strip()
