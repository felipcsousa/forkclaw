from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient
from sqlmodel import select

from app.db.session import get_db_session
from app.models.entities import Approval, TaskRun, ToolCall


def _parse_sse_events(test_client: TestClient, url: str, *, expected_terminal: str) -> list[dict]:
    events: list[dict] = []
    with test_client.stream("GET", url) as response:
        assert response.status_code == 200
        lines = response.iter_lines()
        event_name: str | None = None
        data_lines: list[str] = []
        for raw_line in lines:
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if line.startswith(":"):
                continue
            if not line:
                if event_name and data_lines:
                    payload = json.loads("\n".join(data_lines))
                    assert payload["type"] == event_name
                    events.append(payload)
                    if payload["type"] == expected_terminal:
                        break
                event_name = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())
    return events


def _wait_for_task_run(task_run_id: str, *, status: str, timeout_seconds: float = 3.0) -> TaskRun:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with get_db_session() as session:
            task_run = session.exec(select(TaskRun).where(TaskRun.id == task_run_id)).first()
            if task_run is not None and task_run.status == status:
                return task_run
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for task run {task_run_id} to reach {status}.")


def test_async_session_message_streams_execution_lifecycle(test_client: TestClient) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Async Chat"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    start_response = test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "hello async"},
    )

    assert start_response.status_code == 202
    payload = start_response.json()
    assert payload["session_id"] == session_id
    assert payload["status"] == "queued"
    assert payload["events_url"] == (
        f"/sessions/{session_id}/events?task_run_id={payload['task_run_id']}"
    )

    events = _parse_sse_events(
        test_client,
        payload["events_url"],
        expected_terminal="execution.completed",
    )

    assert [event["type"] for event in events] == [
        "message.user.accepted",
        "assistant.run.created",
        "execution.started",
        "message.completed",
        "execution.completed",
    ]
    assert events[-2]["data"]["message"]["role"] == "assistant"
    assert "Reply: hello async" in events[-2]["data"]["message"]["content_text"]
    assert events[-1]["data"]["status"] == "completed"

    task_run = _wait_for_task_run(payload["task_run_id"], status="completed")
    assert task_run.finished_at is not None


def test_async_stream_includes_tool_events(test_client: TestClient) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Async Tool"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    permission_response = test_client.put(
        "/tools/permissions/list_files",
        json={"permission_level": "allow"},
    )
    assert permission_response.status_code == 200

    start_response = test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "tool:list_files path=."},
    )
    assert start_response.status_code == 202
    payload = start_response.json()

    events = _parse_sse_events(
        test_client,
        payload["events_url"],
        expected_terminal="execution.completed",
    )

    event_types = [event["type"] for event in events]
    assert "tool.started" in event_types
    assert "tool.completed" in event_types

    started_event = next(event for event in events if event["type"] == "tool.started")
    completed_event = next(event for event in events if event["type"] == "tool.completed")
    assert started_event["data"]["tool_name"] == "list_files"
    assert completed_event["data"]["tool_name"] == "list_files"

    with get_db_session() as session:
        tool_call = session.exec(
            select(ToolCall).where(ToolCall.task_run_id == payload["task_run_id"])
        ).first()

    assert tool_call is not None
    assert tool_call.status == "completed"


def test_async_stream_includes_shell_exec_payload_and_execution_timestamps(
    test_client: TestClient,
) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Async Shell"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    permission_response = test_client.put(
        "/tools/permissions/shell_exec",
        json={"permission_level": "allow"},
    )
    assert permission_response.status_code == 200

    start_response = test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "tool:shell_exec command='echo hello' cwd=."},
    )
    assert start_response.status_code == 202
    payload = start_response.json()

    events = _parse_sse_events(
        test_client,
        payload["events_url"],
        expected_terminal="execution.completed",
    )

    assert [event["type"] for event in events] == [
        "message.user.accepted",
        "assistant.run.created",
        "execution.started",
        "tool.started",
        "tool.completed",
        "message.completed",
        "execution.completed",
    ]

    execution_started = next(event for event in events if event["type"] == "execution.started")
    tool_started = next(event for event in events if event["type"] == "tool.started")
    tool_completed = next(event for event in events if event["type"] == "tool.completed")
    execution_completed = next(event for event in events if event["type"] == "execution.completed")

    assert execution_started["data"]["status"] == "running"
    assert execution_started["data"]["started_at"]
    assert execution_started["data"]["finished_at"] is None

    assert tool_started["data"]["tool_name"] == "shell_exec"
    assert tool_started["data"]["status"] == "started"
    assert tool_started["data"]["started_at"]
    assert tool_started["data"]["finished_at"] is None
    assert json.loads(tool_started["data"]["input_json"]) == {
        "command": "echo hello",
        "cwd": ".",
    }

    completed_output = json.loads(tool_completed["data"]["output_json"])
    assert tool_completed["data"]["tool_name"] == "shell_exec"
    assert tool_completed["data"]["status"] == "completed"
    assert tool_completed["data"]["started_at"]
    assert tool_completed["data"]["finished_at"]
    assert "Shell command finished with exit code 0" in tool_completed["data"]["output_text"]
    assert completed_output["text"].startswith("Shell command finished with exit code 0")
    assert completed_output["data"]["stdout"] == "hello\n"
    assert completed_output["data"]["stderr"] == ""
    assert completed_output["data"]["exit_code"] == 0
    assert isinstance(completed_output["data"]["duration_ms"], int)
    assert completed_output["data"]["cwd_resolved"]
    assert completed_output["data"]["truncated"] is False

    assert execution_completed["data"]["status"] == "completed"
    assert execution_completed["data"]["started_at"]
    assert execution_completed["data"]["finished_at"]


def test_async_stream_includes_approval_requested_event(test_client: TestClient) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Async Approval"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    permission_response = test_client.put(
        "/tools/permissions/write_file",
        json={"permission_level": "ask"},
    )
    assert permission_response.status_code == 200

    start_response = test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "tool:write_file path=todo.txt content='secret plan'"},
    )
    assert start_response.status_code == 202
    payload = start_response.json()

    events = _parse_sse_events(
        test_client,
        payload["events_url"],
        expected_terminal="approval.requested",
    )

    assert [event["type"] for event in events] == [
        "message.user.accepted",
        "assistant.run.created",
        "execution.started",
        "tool.started",
        "approval.requested",
    ]
    assert events[-1]["data"]["tool_name"] == "write_file"

    task_run = _wait_for_task_run(payload["task_run_id"], status="awaiting_approval")
    assert task_run.output_json is not None

    with get_db_session() as session:
        approval = session.exec(select(Approval).order_by(Approval.created_at.desc())).first()

    assert approval is not None
    assert approval.status == "pending"


def test_async_stream_reports_failed_execution(test_client: TestClient) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Async Failure"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    permission_response = test_client.put(
        "/tools/permissions/read_file",
        json={"permission_level": "allow"},
    )
    assert permission_response.status_code == 200

    start_response = test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "tool:read_file path=missing.txt"},
    )
    assert start_response.status_code == 202
    payload = start_response.json()

    events = _parse_sse_events(
        test_client,
        payload["events_url"],
        expected_terminal="execution.failed",
    )

    event_types = [event["type"] for event in events]
    assert "tool.started" in event_types
    assert "tool.failed" in event_types
    assert event_types[-1] == "execution.failed"

    task_run = _wait_for_task_run(payload["task_run_id"], status="failed")
    assert task_run.error_message


def test_async_stream_reports_shell_timeout_failure(test_client: TestClient) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Async Shell Timeout"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    permission_response = test_client.put(
        "/tools/permissions/shell_exec",
        json={"permission_level": "allow"},
    )
    assert permission_response.status_code == 200

    start_response = test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "tool:shell_exec command='sleep 2' cwd=. timeout_seconds=1"},
    )
    assert start_response.status_code == 202
    payload = start_response.json()

    events = _parse_sse_events(
        test_client,
        payload["events_url"],
        expected_terminal="execution.failed",
    )

    event_types = [event["type"] for event in events]
    assert "tool.started" in event_types
    assert "tool.failed" in event_types
    assert event_types[-1] == "execution.failed"

    failed_event = next(event for event in events if event["type"] == "tool.failed")
    assert failed_event["data"]["tool_name"] == "shell_exec"
    assert "timed out" in failed_event["data"]["error_message"]

    execution_failed = events[-1]
    assert execution_failed["data"]["status"] == "failed"
    assert "timed out" in execution_failed["data"]["error_message"]
