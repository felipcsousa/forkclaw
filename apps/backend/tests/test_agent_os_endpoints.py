from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import select

from app.db.session import get_db_session
from app.models.entities import (
    Agent,
    AgentProfile,
    Approval,
    AuditEvent,
    CronJob,
    Message,
    Setting,
    Task,
    TaskRun,
    ToolCall,
    ToolPermission,
    utc_now,
)


def _create_pending_write_file_approval(test_client: TestClient) -> tuple[dict, ToolCall, Approval]:
    permission_response = test_client.put(
        "/tools/permissions/write_file",
        json={"permission_level": "ask"},
    )
    assert permission_response.status_code == 200

    execute_response = test_client.post(
        "/agent/execute",
        json={
            "title": "Approval Session",
            "message": "tool:write_file path=todo.txt content='secret plan'",
        },
    )
    assert execute_response.status_code == 201
    payload = execute_response.json()

    with get_db_session() as session:
        tool_call = session.exec(
            select(ToolCall)
            .where(ToolCall.tool_name == "write_file")
            .order_by(ToolCall.created_at.desc())
        ).one()
        approval = session.exec(
            select(Approval)
            .where(Approval.tool_call_id == tool_call.id)
            .order_by(Approval.created_at.desc())
        ).one()

    return payload, tool_call, approval


def _wait_for(predicate, *, timeout: float = 2.5, interval: float = 0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return predicate()


def test_health_check_returns_ok_payload(test_client: TestClient) -> None:
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {
        "status": "ok",
        "service": "backend",
        "version": "0.1.0",
    }


def test_get_agent_returns_seeded_default_agent(test_client: TestClient) -> None:
    response = test_client.get("/agent")

    assert response.status_code == 200
    payload = response.json()

    assert payload["slug"] == "main"
    assert payload["is_default"] is True
    assert payload["profile"]["display_name"] == "Nanobot"
    assert "local-first agent" in payload["profile"]["identity_text"]
    assert "explicit approvals" in payload["profile"]["policy_base_text"]


def test_sessions_are_persisted_in_sqlite(test_client: TestClient) -> None:
    list_response = test_client.get("/sessions")
    assert list_response.status_code == 200
    assert list_response.json() == {"items": []}

    create_response = test_client.post("/sessions", json={"title": "Discovery"})
    assert create_response.status_code == 201
    created = create_response.json()

    assert created["title"] == "Discovery"
    assert created["status"] == "active"

    list_response = test_client.get("/sessions")
    assert list_response.status_code == 200
    items = list_response.json()["items"]

    assert len(items) == 1
    assert items[0]["id"] == created["id"]
    assert items[0]["title"] == "Discovery"


def test_settings_return_seeded_rows(test_client: TestClient) -> None:
    response = test_client.get("/settings")

    assert response.status_code == 200
    items = response.json()["items"]
    keys = {(item["scope"], item["key"]) for item in items}

    assert ("app", "default_agent_slug") in keys
    assert ("app", "timezone") in keys
    assert ("security", "approval_mode") in keys


def test_operational_settings_round_trip_and_sync_workspace(
    test_client: TestClient,
) -> None:
    with get_db_session() as session:
        current_workspace = Path(
            session.exec(
                select(Setting.value_text).where(
                    Setting.scope == "security",
                    Setting.key == "workspace_root",
                )
            ).one()
        )
        new_workspace = current_workspace.parent / "workspace-updated"
        new_workspace.mkdir(parents=True, exist_ok=True)

    response = test_client.put(
        "/settings/operational",
        json={
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "workspace_root": str(new_workspace),
            "max_iterations_per_execution": 1,
            "daily_budget_usd": 0.5,
            "monthly_budget_usd": 10,
            "default_view": "activity",
            "activity_poll_seconds": 5,
            "api_key": "sk-test",
            "clear_api_key": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["model_name"] == "gpt-4o-mini"
    assert payload["workspace_root"] == str(new_workspace)
    assert payload["provider_api_key_configured"] is True

    with get_db_session() as session:
        profile = session.exec(select(AgentProfile)).one()
        workspace_setting = session.exec(
            select(Setting).where(
                Setting.scope == "security",
                Setting.key == "workspace_root",
            )
        ).one()
        file_permissions = list(
            session.exec(
                select(ToolPermission).where(
                    ToolPermission.tool_name.in_(
                        ["list_files", "read_file", "write_file", "edit_file"]
                    )
                )
            )
        )

    assert profile.model_provider == "openai"
    assert profile.model_name == "gpt-4o-mini"
    assert workspace_setting.value_text == str(new_workspace)
    assert {item.workspace_path for item in file_permissions} == {str(new_workspace)}


def test_budget_limit_blocks_new_execution(test_client: TestClient) -> None:
    workspace_root = test_client.get("/settings/operational").json()["workspace_root"]
    update_response = test_client.put(
        "/settings/operational",
        json={
            "provider": "product_echo",
            "model_name": "product-echo/simple",
            "workspace_root": workspace_root,
            "max_iterations_per_execution": 2,
            "daily_budget_usd": 0.000001,
            "monthly_budget_usd": 0.000001,
            "default_view": "chat",
            "activity_poll_seconds": 3,
            "api_key": None,
            "clear_api_key": False,
        },
    )
    assert update_response.status_code == 200

    execute_response = test_client.post(
        "/agent/execute",
        json={"title": "Budget Block", "message": "this should be blocked"},
    )
    assert execute_response.status_code == 400
    assert execute_response.headers["x-request-id"]
    assert execute_response.json()["request_id"] == execute_response.headers["x-request-id"]
    assert "budget exceeded" in execute_response.text.lower()


def test_agent_execute_persists_messages_and_task_run(test_client: TestClient) -> None:
    response = test_client.post(
        "/agent/execute",
        json={
            "title": "Kernel Smoke Test",
            "message": "ping from sqlite",
        },
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["status"] == "completed"
    assert payload["kernel_name"] == "nanobot"
    assert payload["model_name"] == "product-echo/simple"
    assert "Agent: Primary Agent" in payload["output_text"]
    assert "Reply: ping from sqlite" in payload["output_text"]

    with get_db_session() as session:
        persisted_messages = list(
            session.exec(
                select(Message)
                .where(Message.session_id == payload["session_id"])
                .order_by(Message.sequence_number.asc())
            )
        )
        task = session.exec(select(Task).where(Task.id == payload["task_id"])).one()
        task_run = session.exec(
            select(TaskRun).where(TaskRun.id == payload["task_run_id"])
        ).one()
        audit_events = list(
            session.exec(
                select(AuditEvent)
                .where(AuditEvent.entity_id == payload["task_run_id"])
                .order_by(AuditEvent.created_at.asc())
            )
        )

    assert [message.role for message in persisted_messages] == ["user", "assistant"]
    assert persisted_messages[0].content_text == "ping from sqlite"
    assert "Reply: ping from sqlite" in persisted_messages[1].content_text
    assert task.status == "completed"
    assert task.kind == "agent_execution"
    assert task_run.status == "completed"
    assert task_run.output_json is not None
    assert [event.event_type for event in audit_events] == [
        "kernel.execution.started",
        "kernel.execution.completed",
    ]


def test_session_message_routes_round_trip_through_kernel(
    test_client: TestClient,
) -> None:
    create_session_response = test_client.post(
        "/sessions",
        json={"title": "Persistent Chat"},
    )
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    send_response = test_client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "hello chat"},
    )
    assert send_response.status_code == 201
    assert send_response.json()["status"] == "completed"
    assert "Reply: hello chat" in send_response.json()["output_text"]

    messages_response = test_client.get(f"/sessions/{session_id}/messages")
    assert messages_response.status_code == 200

    payload = messages_response.json()
    assert payload["session"]["id"] == session_id
    assert [item["role"] for item in payload["items"]] == ["user", "assistant"]
    assert payload["items"][0]["content_text"] == "hello chat"
    assert "Reply: hello chat" in payload["items"][1]["content_text"]


def test_agent_config_can_be_updated_and_reset(test_client: TestClient) -> None:
    update_response = test_client.put(
        "/agent/config",
        json={
            "name": "Desk Operator",
            "description": "Configuration for a family-office style operator.",
            "identity_text": (
                "Act as a meticulous desktop operator with strong "
                "accounting discipline."
            ),
            "soul_text": "Respond in a calm and exact tone.",
            "user_context_text": "The user prefers short operational answers.",
            "policy_base_text": "Always require explicit approval before sensitive actions.",
            "model_name": "product-echo/tuned",
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()

    assert updated["name"] == "Desk Operator"
    assert updated["description"] == "Configuration for a family-office style operator."
    assert updated["profile"]["identity_text"].startswith("Act as a meticulous")
    assert updated["profile"]["soul_text"] == "Respond in a calm and exact tone."
    assert updated["profile"]["user_context_text"] == "The user prefers short operational answers."
    assert updated["profile"]["policy_base_text"] == (
        "Always require explicit approval before sensitive actions."
    )
    assert updated["profile"]["model_name"] == "product-echo/tuned"

    execute_response = test_client.post(
        "/agent/execute",
        json={"message": "check profile application"},
    )
    assert execute_response.status_code == 201
    output_text = execute_response.json()["output_text"]

    assert "Agent: Desk Operator" in output_text
    assert "Soul: Respond in a calm and exact tone." in output_text
    assert "Policy: Always require explicit approval before sensitive actions." in output_text

    reset_response = test_client.post("/agent/config/reset")
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()

    assert reset_payload["name"] == "Primary Agent"
    assert reset_payload["profile"]["model_name"] == "product-echo/simple"
    assert "local-first agent" in reset_payload["profile"]["identity_text"]


def test_tool_permissions_are_listed_and_updatable(test_client: TestClient) -> None:
    response = test_client.get("/tools/permissions")
    assert response.status_code == 200
    payload = response.json()

    assert payload["workspace_root"].endswith("/workspace")
    assert {item["tool_name"] for item in payload["items"]} >= {
        "list_files",
        "read_file",
        "write_file",
        "edit_file",
        "clipboard_read",
        "clipboard_write",
    }

    update_response = test_client.put(
        "/tools/permissions/list_files",
        json={"permission_level": "allow"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["permission_level"] == "allow"


def test_agent_can_use_allowed_tool_and_persist_tool_call(test_client: TestClient) -> None:
    permission_response = test_client.put(
        "/tools/permissions/list_files",
        json={"permission_level": "allow"},
    )
    assert permission_response.status_code == 200

    execute_response = test_client.post(
        "/agent/execute",
        json={"message": "tool:list_files path=."},
    )
    assert execute_response.status_code == 201
    payload = execute_response.json()

    assert payload["status"] == "completed"
    assert "Tool result from list_files" in payload["output_text"]
    assert "notes.txt" in payload["output_text"]
    assert "list_files" in payload["tools_used"]

    with get_db_session() as session:
        tool_calls = list(session.exec(select(ToolCall).order_by(ToolCall.created_at.desc())))

    assert tool_calls[0].tool_name == "list_files"
    assert tool_calls[0].status == "completed"


def test_agent_cannot_use_denied_tool(test_client: TestClient) -> None:
    permission_response = test_client.put(
        "/tools/permissions/read_file",
        json={"permission_level": "deny"},
    )
    assert permission_response.status_code == 200

    execute_response = test_client.post(
        "/agent/execute",
        json={"message": "tool:read_file path=notes.txt"},
    )
    assert execute_response.status_code == 201
    payload = execute_response.json()

    assert payload["status"] == "completed"
    assert "denied by policy" in payload["output_text"]

    with get_db_session() as session:
        tool_call = session.exec(
            select(ToolCall)
            .where(ToolCall.tool_name == "read_file")
            .order_by(ToolCall.created_at.desc())
        ).first()

    assert tool_call is not None
    assert tool_call.status == "denied"


def test_ask_mode_pauses_execution_and_creates_pending_approval(
    test_client: TestClient,
) -> None:
    payload, tool_call, approval = _create_pending_write_file_approval(test_client)

    assert payload["status"] == "awaiting_approval"
    assert "requires approval" in payload["output_text"]

    with get_db_session() as session:
        task_run = session.exec(
            select(TaskRun).where(TaskRun.id == payload["task_run_id"])
        ).one()
        task = session.exec(select(Task).where(Task.id == payload["task_id"])).one()
        persisted_messages = list(
            session.exec(
                select(Message)
                .where(Message.session_id == payload["session_id"])
                .order_by(Message.sequence_number.asc())
            )
        )

    assert tool_call.status == "awaiting_approval"
    assert approval.status == "pending"
    assert task.status == "awaiting_approval"
    assert task_run.status == "awaiting_approval"
    assert [message.role for message in persisted_messages] == ["user", "assistant"]
    assert "requires approval" in persisted_messages[-1].content_text


def test_list_approvals_returns_pending_items(test_client: TestClient) -> None:
    _, _, approval = _create_pending_write_file_approval(test_client)

    response = test_client.get("/approvals")
    assert response.status_code == 200
    items = response.json()["items"]

    assert len(items) == 1
    assert items[0]["id"] == approval.id
    assert items[0]["status"] == "pending"
    assert items[0]["tool_name"] == "write_file"
    assert items[0]["session_title"] == "Approval Session"
    assert "todo.txt" in (items[0]["tool_input_json"] or "")


def test_approve_executes_tool_and_resumes_kernel(test_client: TestClient) -> None:
    payload, tool_call, approval = _create_pending_write_file_approval(test_client)
    permissions_response = test_client.get("/tools/permissions")
    workspace_root = Path(permissions_response.json()["workspace_root"])

    approve_response = test_client.post(f"/approvals/{approval.id}/approve")
    assert approve_response.status_code == 200
    approval_payload = approve_response.json()

    assert approval_payload["approval"]["status"] == "approved"
    assert approval_payload["task_run_status"] == "completed"
    assert approval_payload["tool_call_status"] == "completed"
    assert "Tool result from write_file" in approval_payload["output_text"]
    assert "Wrote 11 characters to todo.txt." in approval_payload["output_text"]

    written_file = workspace_root / "todo.txt"
    assert written_file.exists()
    assert written_file.read_text(encoding="utf-8") == "secret plan"

    with get_db_session() as session:
        refreshed_tool_call = session.exec(
            select(ToolCall).where(ToolCall.id == tool_call.id)
        ).one()
        refreshed_approval = session.exec(
            select(Approval).where(Approval.id == approval.id)
        ).one()
        refreshed_task_run = session.exec(
            select(TaskRun).where(TaskRun.id == payload["task_run_id"])
        ).one()
        persisted_messages = list(
            session.exec(
                select(Message)
                .where(Message.session_id == payload["session_id"])
                .order_by(Message.sequence_number.asc())
            )
        )
        audit_events = list(
            session.exec(
                select(AuditEvent)
                .where(AuditEvent.entity_id.in_([approval.id, payload["task_run_id"]]))
                .order_by(AuditEvent.created_at.asc())
            )
        )

    assert refreshed_tool_call.status == "completed"
    assert refreshed_approval.status == "approved"
    assert refreshed_task_run.status == "completed"
    assert [message.role for message in persisted_messages] == ["user", "assistant", "assistant"]
    assert "Wrote 11 characters to todo.txt." in persisted_messages[-1].content_text
    assert {event.event_type for event in audit_events} >= {
        "approval.approved",
        "kernel.execution.awaiting_approval",
        "kernel.execution.completed",
    }


def test_deny_marks_execution_failed_with_traceability(test_client: TestClient) -> None:
    payload, tool_call, approval = _create_pending_write_file_approval(test_client)

    deny_response = test_client.post(f"/approvals/{approval.id}/deny")
    assert deny_response.status_code == 200
    deny_payload = deny_response.json()

    assert deny_payload["approval"]["status"] == "denied"
    assert deny_payload["task_run_status"] == "failed"
    assert deny_payload["tool_call_status"] == "denied"
    assert "Approval denied" in deny_payload["output_text"]

    with get_db_session() as session:
        refreshed_tool_call = session.exec(
            select(ToolCall).where(ToolCall.id == tool_call.id)
        ).one()
        refreshed_approval = session.exec(
            select(Approval).where(Approval.id == approval.id)
        ).one()
        refreshed_task_run = session.exec(
            select(TaskRun).where(TaskRun.id == payload["task_run_id"])
        ).one()
        persisted_messages = list(
            session.exec(
                select(Message)
                .where(Message.session_id == payload["session_id"])
                .order_by(Message.sequence_number.asc())
            )
        )
        audit_events = list(
            session.exec(
                select(AuditEvent)
                .where(AuditEvent.entity_id.in_([approval.id, payload["task_run_id"]]))
                .order_by(AuditEvent.created_at.asc())
            )
        )

    assert refreshed_tool_call.status == "denied"
    assert refreshed_approval.status == "denied"
    assert refreshed_task_run.status == "failed"
    assert [message.role for message in persisted_messages] == ["user", "assistant", "assistant"]
    assert "Approval denied for `write_file`" in persisted_messages[-1].content_text
    assert {event.event_type for event in audit_events} >= {
        "approval.denied",
        "kernel.execution.awaiting_approval",
    }


def test_write_file_permission_stays_persisted_as_ask(test_client: TestClient) -> None:
    _, _, _ = _create_pending_write_file_approval(test_client)

    with get_db_session() as session:
        permission = session.exec(
            select(ToolPermission)
            .where(ToolPermission.tool_name == "write_file")
            .order_by(ToolPermission.created_at.desc())
        ).one()

    assert permission.permission_level == "ask"


def test_activity_timeline_aggregates_execution_in_product_order(
    test_client: TestClient,
) -> None:
    permission_response = test_client.put(
        "/tools/permissions/list_files",
        json={"permission_level": "allow"},
    )
    assert permission_response.status_code == 200

    execute_response = test_client.post(
        "/agent/execute",
        json={"title": "Timeline Session", "message": "tool:list_files path=."},
    )
    assert execute_response.status_code == 201

    response = test_client.get("/activity/timeline")
    assert response.status_code == 200
    item = response.json()["items"][0]

    assert item["task_kind"] == "agent_execution"
    assert item["session_title"] == "Timeline Session"
    assert item["duration_ms"] is not None
    assert item["estimated_cost_usd"] is not None

    entry_types = [entry["type"] for entry in item["entries"]]
    assert entry_types[:3] == ["message", "task", "tool_call"]
    assert entry_types[-1] in {"status", "audit"}
    assert any(entry["title"] == "Execution status" for entry in item["entries"])
    assert any("list_files" in entry["title"] for entry in item["entries"])


def test_activity_timeline_surfaces_failures_clearly(test_client: TestClient) -> None:
    permission_response = test_client.put(
        "/tools/permissions/read_file",
        json={"permission_level": "deny"},
    )
    assert permission_response.status_code == 200

    execute_response = test_client.post(
        "/agent/execute",
        json={"title": "Failure Session", "message": "tool:read_file path=missing.txt"},
    )
    assert execute_response.status_code == 201

    response = test_client.get("/activity/timeline")
    assert response.status_code == 200
    item = next(
        current
        for current in response.json()["items"]
        if current["session_title"] == "Failure Session"
    )

    assert item["status"] == "completed"
    assert any(entry["type"] == "tool_call" for entry in item["entries"])
    tool_entry = next(entry for entry in item["entries"] if entry["type"] == "tool_call")
    assert tool_entry["status"] == "denied"
    assert "denied by policy" in tool_entry["summary"]


def test_cron_job_can_be_created_and_runs_automatically(test_client: TestClient) -> None:
    create_response = test_client.post(
        "/cron-jobs",
        json={
            "name": "Recent Activity Digest",
            "schedule": "every:1s",
            "payload": {
                "job_type": "summarize_recent_activity",
                "message": "Automatic smoke test.",
            },
        },
    )
    assert create_response.status_code == 201
    job = create_response.json()

    assert job["status"] == "active"
    assert job["next_run_at"] is not None

    history = _wait_for(
        lambda: [
            item
            for item in test_client.get("/cron-jobs").json()["history"]
            if item["cron_job_id"] == job["id"] and item["status"] == "completed"
        ]
        or None,
        timeout=2.5,
        interval=0.2,
    )
    assert history
    assert history[0]["job_name"] == "Recent Activity Digest"
    assert "Recent activity in the last 24h" in (history[0]["output_summary"] or "")

    dashboard = test_client.get("/cron-jobs").json()
    refreshed_job = next(item for item in dashboard["items"] if item["id"] == job["id"])
    assert refreshed_job["last_run_at"] is not None
    assert refreshed_job["next_run_at"] is not None

    with get_db_session() as session:
        persisted_job = session.exec(select(CronJob).where(CronJob.id == job["id"])).one()
        persisted_task = session.exec(select(Task).where(Task.cron_job_id == job["id"])).one()

    assert persisted_job.last_run_at is not None
    assert persisted_task.kind == "cron_job"


def test_cron_job_can_be_paused_activated_and_removed(test_client: TestClient) -> None:
    create_response = test_client.post(
        "/cron-jobs",
        json={
            "name": "Pending Approval Sweep",
            "schedule": "every:2s",
            "payload": {"job_type": "review_pending_approvals"},
        },
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    pause_response = test_client.post(f"/cron-jobs/{job_id}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"
    assert pause_response.json()["next_run_at"] is None

    activated_response = test_client.post(f"/cron-jobs/{job_id}/activate")
    assert activated_response.status_code == 200
    assert activated_response.json()["status"] == "active"
    assert activated_response.json()["next_run_at"] is not None

    delete_response = test_client.delete(f"/cron-jobs/{job_id}")
    assert delete_response.status_code == 204

    dashboard = test_client.get("/cron-jobs")
    assert dashboard.status_code == 200
    assert all(item["id"] != job_id for item in dashboard.json()["items"])


def test_heartbeat_records_activity_and_cleans_stale_runs(test_client: TestClient) -> None:
    with get_db_session() as session:
        agent_id = session.exec(select(Agent.id).where(Agent.is_default.is_(True))).one()
        stale_task = Task(
            agent_id=agent_id,
            cron_job_id=None,
            session_id=None,
            title="Stale heartbeat target",
            kind="cron_job",
            status="running",
            payload_json=None,
        )
        session.add(stale_task)
        session.commit()
        session.refresh(stale_task)

        stale_run = TaskRun(
            task_id=stale_task.id,
            status="running",
            attempt=1,
            started_at=utc_now() - timedelta(seconds=5),
        )
        session.add(stale_run)
        session.commit()
        stale_run_id = stale_run.id

    dashboard = _wait_for(
        lambda: (
            lambda current: current
            if current["heartbeat"]["last_run_at"] is not None
            and current["heartbeat"]["cleaned_stale_runs"] >= 1
            else None
        )(test_client.get("/cron-jobs").json()),
        timeout=2.5,
        interval=0.2,
    )

    assert dashboard["heartbeat"]["last_run_at"] is not None
    assert dashboard["heartbeat"]["recent_task_runs"] >= 1
    assert "Heartbeat reviewed" in dashboard["heartbeat"]["summary_text"]

    with get_db_session() as session:
        refreshed_run = session.exec(select(TaskRun).where(TaskRun.id == stale_run_id)).one()

    assert refreshed_run.status == "failed"
    assert refreshed_run.error_message == "Marked as failed by heartbeat after stale timeout."
