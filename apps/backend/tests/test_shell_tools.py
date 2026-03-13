from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from app.tools.base import ToolExecutionContext
from app.tools.registry import build_tool_registry


def _shell_tool():
    return build_tool_registry().get("shell_exec")


def _context(workspace_root: Path, **runtime_settings) -> ToolExecutionContext:
    return ToolExecutionContext(
        workspace_root=workspace_root,
        runtime_settings={
            "tool_timeout_seconds": 5.0,
            "shell_exec_max_output_chars": 8192,
            "shell_exec_allowed_cwd_roots": [],
            "shell_exec_allowed_env_keys": ["PATH"],
            **runtime_settings,
        },
    )


def test_shell_exec_runs_command_inside_workspace(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    project_root = workspace_root / "project"
    project_root.mkdir(parents=True)

    result = _shell_tool().execute(
        context=_context(workspace_root),
        arguments={"command": "pwd", "cwd": "project"},
    )

    assert result.output_data == {
        "stdout": f"{project_root.resolve()}\n",
        "stderr": "",
        "exit_code": 0,
        "duration_ms": pytest.approx(result.output_data["duration_ms"], rel=0, abs=500),
        "cwd_resolved": str(project_root.resolve()),
        "truncated": False,
    }


def test_shell_exec_allows_absolute_cwd_inside_allowlist(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    allowed_root = tmp_path / "external-allowed"
    allowed_root.mkdir()

    result = _shell_tool().execute(
        context=_context(
            workspace_root,
            shell_exec_allowed_cwd_roots=[str(allowed_root)],
        ),
        arguments={"command": "pwd", "cwd": str(allowed_root)},
    )

    assert result.output_data is not None
    assert result.output_data["cwd_resolved"] == str(allowed_root.resolve())
    assert result.output_data["exit_code"] == 0


def test_shell_exec_returns_nonzero_exit_codes_without_raising(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    result = _shell_tool().execute(
        context=_context(workspace_root),
        arguments={"command": "echo boom >&2; exit 7"},
    )

    assert result.output_data is not None
    assert result.output_data["exit_code"] == 7
    assert result.output_data["stderr"] == "boom\n"


def test_shell_exec_times_out_with_clear_error(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    with pytest.raises(TimeoutError, match="timed out"):
        _shell_tool().execute(
            context=_context(workspace_root, tool_timeout_seconds=1.0),
            arguments={"command": "sleep 2", "timeout_seconds": 1},
        )


def test_shell_exec_rejects_cwd_outside_workspace_and_allowlist(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    forbidden_root = tmp_path / "forbidden"
    forbidden_root.mkdir()

    with pytest.raises(PermissionError, match="allowlist"):
        _shell_tool().execute(
            context=_context(workspace_root),
            arguments={"command": "pwd", "cwd": str(forbidden_root)},
        )


def test_shell_exec_marks_large_output_as_truncated(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    command = f"{shlex.quote(sys.executable)} -c \"print('x' * 400)\""

    result = _shell_tool().execute(
        context=_context(workspace_root, shell_exec_max_output_chars=120),
        arguments={"command": command},
    )

    assert result.output_data is not None
    assert result.output_data["truncated"] is True
    assert len(result.output_data["stdout"]) <= 120


def test_shell_exec_rejects_env_keys_outside_allowlist(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    with pytest.raises(PermissionError, match="Environment variable"):
        _shell_tool().execute(
            context=_context(workspace_root, shell_exec_allowed_env_keys=["PATH"]),
            arguments={
                "command": "pwd",
                "env": {"SECRET_TOKEN": "value"},
            },
        )
