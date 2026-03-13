from __future__ import annotations

import asyncio
import json
import time

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.routes.sessions import stream_session_events
from app.db.session import get_db_session
from app.models.entities import Approval, TaskRun, ToolCall
from app.services.execution_events import ExecutionEventService


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


def _parse_sse_frames(
    test_client: TestClient,
    url: str,
    *,
    expected_terminal: str,
    headers: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    frames: list[dict[str, object]] = []
    with test_client.stream("GET", url, headers=headers or {}) as response:
        assert response.status_code == 200
        lines = response.iter_lines()
        event_name: str | None = None
        data_lines: list[str] = []
        event_id: str | None = None
        for raw_line in lines:
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if line.startswith(":"):
                continue
            if not line:
                if event_name and data_lines:
                    payload = json.loads("\n".join(data_lines))
                    frames.append(
                        {
                            "event": event_name,
                            "event_id": event_id,
                            "payload": payload,
                        }
                    )
                    if event_name == expected_terminal:
                        break
                event_name = None
                data_lines = []
                event_id = None
                continue
            if line.startswith("id:"):
                event_id = line.split(":", 1)[1].strip()
            elif line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())
    return frames


async def _collect_stream_response_frames(response) -> list[dict[str, object]]:
    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))

    frames: list[dict[str, object]] = []
    event_name: str | None = None
    data_lines: list[str] = []
    event_id: str | None = None
    for raw_line in "".join(chunks).splitlines():
        line = raw_line.rstrip("\n").rstrip("\r")
        if line.startswith(":"):
            continue
        if not line:
            if event_name and data_lines:
                frames.append(
                    {
                        "event": event_name,
                        "event_id": event_id,
                        "payload": json.loads("\n".join(data_lines)),
                    }
                )
            event_name = None
            data_lines = []
            event_id = None
            continue
        if line.startswith("id:"):
            event_id = line.split(":", 1)[1].strip()
        elif line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
    return frames


class _DisconnectAfterReplayRequest:
    async def is_disconnected(self) -> bool:
        return True


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


def test_session_stream_emits_stream_ready_after_replay_without_event_id(
    test_client: TestClient,
) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Replay Ready"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    start_response = test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "hello replay"},
    )
    assert start_response.status_code == 202
    payload = start_response.json()

    _wait_for_task_run(payload["task_run_id"], status="completed")

    response = asyncio.run(
        stream_session_events(
            session_id=session_id,
            request=_DisconnectAfterReplayRequest(),
            task_run_id=None,
            last_event_id=None,
        )
    )
    frames = asyncio.run(_collect_stream_response_frames(response))

    assert [frame["event"] for frame in frames] == [
        "message.user.accepted",
        "assistant.run.created",
        "execution.started",
        "message.completed",
        "execution.completed",
        "stream.ready",
    ]
    ready_frame = frames[-1]
    assert ready_frame["event_id"] is None
    assert ready_frame["payload"] == {
        "type": "stream.ready",
        "session_id": session_id,
        "data": {"phase": "live"},
    }


def test_task_run_stream_does_not_emit_stream_ready(test_client: TestClient) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Finite Stream"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    start_response = test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "hello finite"},
    )
    assert start_response.status_code == 202
    payload = start_response.json()

    frames = _parse_sse_frames(
        test_client,
        payload["events_url"],
        expected_terminal="execution.completed",
    )
    assert [frame["event"] for frame in frames] == [
        "message.user.accepted",
        "assistant.run.created",
        "execution.started",
        "message.completed",
        "execution.completed",
    ]
    assert all(frame["event"] != "stream.ready" for frame in frames)


def test_session_stream_reconnect_replays_only_events_after_last_event_id(
    test_client: TestClient,
) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Reconnect Ready"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    start_response = test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "hello reconnect"},
    )
    assert start_response.status_code == 202
    payload = start_response.json()

    _wait_for_task_run(payload["task_run_id"], status="completed")

    initial_response = asyncio.run(
        stream_session_events(
            session_id=session_id,
            request=_DisconnectAfterReplayRequest(),
            task_run_id=None,
            last_event_id=None,
        )
    )
    initial_frames = asyncio.run(_collect_stream_response_frames(initial_response))
    persisted_frames = [frame for frame in initial_frames if frame["event"] != "stream.ready"]
    last_event_id = persisted_frames[0]["event_id"]
    assert isinstance(last_event_id, str)

    replay_response = asyncio.run(
        stream_session_events(
            session_id=session_id,
            request=_DisconnectAfterReplayRequest(),
            task_run_id=None,
            last_event_id=last_event_id,
        )
    )
    replay_frames = asyncio.run(_collect_stream_response_frames(replay_response))
    assert [frame["event"] for frame in replay_frames] == [
        "assistant.run.created",
        "execution.started",
        "message.completed",
        "execution.completed",
        "stream.ready",
    ]
    assert replay_frames[-1]["event_id"] is None


def test_execution_event_service_filters_audit_event_query_by_scope(
    monkeypatch, test_client
) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Scoped Events"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    test_client.post(
        f"/sessions/{session_id}/messages/async",
        json={"content": "hello scope"},
    )

    with get_db_session() as session:
        service = ExecutionEventService(session)
        original_exec = session.exec

        def wrapped_exec(statement, *args, **kwargs):
            entity = getattr(statement, "column_descriptions", [{}])[0].get("entity")
            if entity is not None and entity.__name__ == "AuditEvent":
                assert getattr(statement, "_where_criteria", ())
            return original_exec(statement, *args, **kwargs)

        monkeypatch.setattr(session, "exec", wrapped_exec)
        service.list_events(session_id=session_id)
