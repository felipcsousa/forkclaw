from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from nanobot.providers.base import LLMResponse
from sqlmodel import select

from alembic import command
from app.core.config import clear_settings_cache, get_settings
from app.core.secrets import clear_secret_store_cache
from app.db.seed import seed_default_data
from app.db.session import clear_engine_cache, get_db_session
from app.kernel.contracts import KernelMemoryRecall, KernelMemoryRecallItem
from app.models.entities import (
    MemoryEntry,
    Message,
    SessionRecord,
    SessionSubagentRun,
    Setting,
    ToolPermission,
    utc_now,
)
from app.repositories.agent_execution import AgentExecutionRepository
from app.repositories.subagents import SubagentRepository
from app.schemas.session import SubagentSpawnRequest
from app.services.agent_os import AgentOSService
from app.services.execution_request_builder import ExecutionRequestBuilder
from app.services.subagent_tool_scoping import resolve_subagent_tool_scope
from app.services.subagents import SubagentDelegationService


def _wait_for(predicate, *, timeout: float = 3.0, interval: float = 0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return predicate()


def _set_feature_flag(key: str, enabled: bool) -> None:
    with get_db_session() as session:
        setting = session.exec(
            select(Setting).where(Setting.scope == "features", Setting.key == key)
        ).one()
        setting.value_text = "true" if enabled else "false"
        session.add(setting)
        session.commit()


def _alembic_config() -> Config:
    settings = get_settings()
    config = Config(str(settings.backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(settings.backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


@contextmanager
def _isolated_backend(tmp_path: Path, monkeypatch):
    database_path = tmp_path / "agent_os_test.db"
    workspace_root = tmp_path / "workspace"
    bundled_skills_root = tmp_path / "bundled-skills"
    workspace_root.mkdir(parents=True, exist_ok=True)
    bundled_skills_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "notes.txt").write_text("hello workspace", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_WORKSPACE_ROOT", str(workspace_root))
    monkeypatch.setenv("APP_BUNDLED_SKILLS_ROOT", str(bundled_skills_root))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SCHEDULER_POLL_INTERVAL_SECONDS", "0.2")
    monkeypatch.setenv("SUBAGENT_WORKER_POLL_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("SUBAGENT_RUN_TIMEOUT_SECONDS", "1.0")
    monkeypatch.setenv("SUBAGENT_MAX_RUN_TIMEOUT_SECONDS", "2.0")
    monkeypatch.setenv("SUBAGENT_STUCK_GRACE_SECONDS", "0.1")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "1800")
    monkeypatch.setenv("STALE_TASK_RUN_SECONDS", "1")
    monkeypatch.setenv("APP_SECRET_BACKEND", "memory")

    clear_settings_cache()
    clear_secret_store_cache()
    clear_engine_cache()

    command.upgrade(_alembic_config(), "head")
    with get_db_session() as session:
        seed_default_data(session)

    try:
        yield
    finally:
        clear_engine_cache()
        clear_settings_cache()
        clear_secret_store_cache()


def test_resolve_subagent_tool_scope_respects_requested_groups_and_deny_wins() -> None:
    permissions = [
        ToolPermission(
            agent_id="agent-1",
            tool_name="list_files",
            workspace_path="/tmp/workspace",
            permission_level="allow",
            approval_required=False,
            status="active",
        ),
        ToolPermission(
            agent_id="agent-1",
            tool_name="read_file",
            workspace_path="/tmp/workspace",
            permission_level="deny",
            approval_required=False,
            status="active",
        ),
        ToolPermission(
            agent_id="agent-1",
            tool_name="web_search",
            workspace_path=None,
            permission_level="ask",
            approval_required=True,
            status="active",
        ),
    ]

    resolution = resolve_subagent_tool_scope(
        requested_toolsets=["file", "web", "terminal", "local_product_tools"],
        tool_permissions=permissions,
    )

    assert resolution.requested_toolsets == ["file", "web", "terminal", "local_product_tools"]
    assert resolution.empty_groups == ["local_product_tools"]
    assert resolution.allowed_tool_names == ["list_files", "web_search"]
    assert resolution.denied_tool_names == ["read_file"]
    assert [item.tool_name for item in resolution.effective_permissions] == [
        "list_files",
        "read_file",
        "web_search",
    ]
    assert resolution.effective_permissions[1].permission_level == "deny"


def test_resolve_subagent_tool_scope_rejects_invalid_group() -> None:
    try:
        resolve_subagent_tool_scope(
            requested_toolsets=["unknown-group"],
            tool_permissions=[],
        )
    except ValueError as exc:
        assert "unknown-group" in str(exc)
        assert "supported toolsets" in str(exc).lower()
    else:
        raise AssertionError("Expected invalid group to raise ValueError.")


def test_resolve_subagent_tool_scope_rejects_legacy_default_group() -> None:
    try:
        resolve_subagent_tool_scope(
            requested_toolsets=["default"],
            tool_permissions=[],
        )
    except ValueError as exc:
        assert "default" in str(exc)
        assert "supported toolsets" in str(exc).lower()
    else:
        raise AssertionError("Expected legacy `default` group to raise ValueError.")


def test_resolve_subagent_tool_scope_maps_terminal_to_shell_exec() -> None:
    permissions = [
        ToolPermission(
            agent_id="agent-1",
            tool_name="shell_exec",
            workspace_path="/tmp/workspace",
            permission_level="allow",
            approval_required=False,
            status="active",
        ),
    ]

    resolution = resolve_subagent_tool_scope(
        requested_toolsets=["terminal"],
        tool_permissions=permissions,
    )

    assert resolution.requested_toolsets == ["terminal"]
    assert resolution.empty_groups == []
    assert resolution.allowed_tool_names == ["shell_exec"]


def test_build_delegated_request_preserves_empty_tool_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _isolated_backend(tmp_path, monkeypatch):
        with get_db_session() as session:
            repository = AgentExecutionRepository(session)
            agent = repository.get_default_agent()
            assert agent is not None
            profile = repository.get_agent_profile(agent.id)
            assert profile is not None

            session_record = repository.create_main_session(agent_id=agent.id, title="Delegated")
            task = repository.create_task(
                agent.id,
                session_record.id,
                {"goal": "Run with no tools"},
                title="Subagent delegated execution",
                kind="subagent_execution",
            )
            task_run = repository.create_task_run(task.id)

            request = ExecutionRequestBuilder(session, repository=repository).build_delegated(
                task=task,
                task_run=task_run,
                session_record=session_record,
                goal="Run with no tools",
                context_snapshot="(none)",
                parent_session_snapshot="Parent session: Delegated",
                allowed_tool_permissions=[],
                model_override=None,
                max_iterations_override=None,
            )

        assert request.tools == []


def test_serialize_memory_recall_includes_query_text(tmp_path: Path, monkeypatch) -> None:
    with _isolated_backend(tmp_path, monkeypatch):
        with get_db_session() as session:
            repository = AgentExecutionRepository(session)
            agent = repository.get_default_agent()
            assert agent is not None

            session_record = repository.create_main_session(
                agent_id=agent.id,
                title="Recall Serialization",
            )
            task = repository.create_task(
                agent.id,
                session_record.id,
                {"goal": "Serialize recall payload"},
                title="Subagent delegated execution",
                kind="subagent_execution",
            )
            task_run = repository.create_task_run(task.id)
            builder = ExecutionRequestBuilder(session, repository=repository)
            request = builder.build_delegated(
                task=task,
                task_run=task_run,
                session_record=session_record,
                goal="Serialize recall payload",
                context_snapshot="(none)",
                parent_session_snapshot="Parent session: Recall Serialization",
                allowed_tool_permissions=[],
                model_override=None,
                max_iterations_override=None,
            )

            with_recall = replace(
                request,
                memory_recall=KernelMemoryRecall(
                    reason_summary="1 memory item(s) injected for recall.",
                    query_text="serialized recall query",
                    items=[
                        KernelMemoryRecallItem(
                            memory_id="memory-1",
                            title="Runtime memory",
                            kind="session_summary",
                            scope="session:memory-1",
                            source_kind="summary",
                            source_label="Session summary",
                            importance="medium",
                            reason="matched current session",
                        )
                    ],
                ),
            )
            payload = builder.serialize_memory_recall(with_recall)

        assert payload is not None
        assert payload["query_text"] == "serialized recall query"


def test_split_persisted_context_snapshot_avoids_parent_duplication() -> None:
    snapshot = (
        "Explicit context:\nFocus on docs.\n\nParent snapshot:\nParent session: Main\n- user: hello"
    )

    explicit_context, parent_snapshot = SubagentDelegationService._split_persisted_context_snapshot(
        snapshot
    )
    prompt = ExecutionRequestBuilder.build_delegated_input(
        goal="Summarize",
        context_snapshot=explicit_context,
        parent_session_snapshot=parent_snapshot,
    )

    assert explicit_context == "Focus on docs."
    assert parent_snapshot == "Parent session: Main\n- user: hello"
    assert prompt.count("Parent snapshot:") == 1
    assert prompt.count("Explicit context:") == 1


def test_spawned_subagent_is_processed_to_completion_and_posts_parent_summary(
    test_client: TestClient,
) -> None:
    parent_response = test_client.post("/sessions", json={"title": "Delegation Parent"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    spawn_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={
            "goal": "Inspect the workspace and produce a short summary.",
            "context": "Focus on the top-level notes file.",
            "toolsets": ["file"],
            "model": "product-echo/simple",
            "max_iterations": 2,
        },
    )
    assert spawn_response.status_code == 201
    child_id = spawn_response.json()["child_session_id"]

    detail_payload = _wait_for(
        lambda: (
            lambda payload: payload if payload["run"]["lifecycle_status"] == "completed" else None
        )(test_client.get(f"/sessions/{parent_id}/subagents/{child_id}").json()),
    )

    assert detail_payload["id"] == child_id
    assert detail_payload["run"]["lifecycle_status"] == "completed"
    assert detail_payload["run"]["final_summary"]
    assert detail_payload["timeline_events"]
    assert [event["event_type"] for event in detail_payload["timeline_events"]] == [
        "subagent.spawned",
        "subagent.started",
        "subagent.completed",
    ]
    final_output = json.loads(detail_payload["run"]["final_output_json"])
    assert final_output["status"] == "completed"
    assert final_output["goal"] == "Inspect the workspace and produce a short summary."
    assert isinstance(final_output["tools_used"], list)
    assert isinstance(final_output["files_touched"], list)

    nested_messages = test_client.get(f"/sessions/{parent_id}/subagents/{child_id}/messages")
    assert nested_messages.status_code == 200
    nested_payload = nested_messages.json()
    assert nested_payload["session"]["id"] == child_id
    assert all(item["session_id"] == child_id for item in nested_payload["items"])
    assert any(item["role"] == "assistant" for item in nested_payload["items"])

    parent_messages = test_client.get(f"/sessions/{parent_id}/messages")
    assert parent_messages.status_code == 200
    assistant_messages = [
        item for item in parent_messages.json()["items"] if item["role"] == "assistant"
    ]
    assert assistant_messages
    assert "subagent" in assistant_messages[-1]["content_text"].lower()
    assert "raw_payload" not in assistant_messages[-1]["content_text"]

    counted_response = test_client.get("/sessions?include_subagent_counts=true")
    assert counted_response.status_code == 200
    counted_item = counted_response.json()["items"][0]
    assert counted_item["subagent_counts"]["completed"] == 1


def test_subagent_uses_only_current_parent_conversation_snapshot_and_writes_scoped_memory(
    test_client: TestClient,
) -> None:
    _set_feature_flag("memory_v1_enabled", True)
    parent_response = test_client.post("/sessions", json={"title": "Scoped Parent"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    old_message = test_client.post(
        f"/sessions/{parent_id}/messages",
        json={"content": "old conversation detail"},
    )
    assert old_message.status_code == 201

    reset_response = test_client.post(f"/sessions/{parent_id}/reset")
    assert reset_response.status_code == 200

    new_message = test_client.post(
        f"/sessions/{parent_id}/messages",
        json={"content": "current conversation detail"},
    )
    assert new_message.status_code == 201

    spawn_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={
            "goal": "Inspect only the current parent context.",
            "context": "Focus on recent context only.",
            "toolsets": ["file"],
        },
    )
    assert spawn_response.status_code == 201
    child_id = spawn_response.json()["child_session_id"]

    detail_payload = _wait_for(
        lambda: (
            lambda payload: payload if payload["run"]["lifecycle_status"] == "completed" else None
        )(test_client.get(f"/sessions/{parent_id}/subagents/{child_id}").json()),
    )
    assert detail_payload is not None

    with get_db_session() as session:
        child = session.exec(select(SessionRecord).where(SessionRecord.id == child_id)).one()
        episodic_memories = list(
            session.exec(
                select(MemoryEntry).where(
                    MemoryEntry.session_id == child_id,
                    MemoryEntry.scope_type == "episodic",
                )
            )
        )

    assert "current conversation detail" in (child.delegated_context_snapshot or "")
    assert "old conversation detail" not in (child.delegated_context_snapshot or "")
    assert episodic_memories
    assert {item.parent_session_id for item in episodic_memories} == {parent_id}
    assert {item.conversation_id for item in episodic_memories} == {child.conversation_id}


def test_spawn_subagent_timeout_defaults_override_and_clamp(
    test_client: TestClient,
) -> None:
    parent_response = test_client.post("/sessions", json={"title": "Timeout Contract Parent"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    default_timeout_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={
            "goal": "Use the backend default timeout.",
            "toolsets": ["file"],
            "model": "product-echo/simple",
        },
    )
    assert default_timeout_response.status_code == 201
    default_timeout_payload = default_timeout_response.json()
    assert default_timeout_payload["timeout_seconds"] == 1.0

    default_detail = test_client.get(
        f"/sessions/{parent_id}/subagents/{default_timeout_payload['child_session_id']}"
    )
    assert default_detail.status_code == 200
    assert default_detail.json()["timeout_seconds"] == 1.0

    overridden_timeout_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={
            "goal": "Override the timeout.",
            "toolsets": ["file"],
            "model": "product-echo/simple",
            "timeout_seconds": 0.5,
        },
    )
    assert overridden_timeout_response.status_code == 201
    assert overridden_timeout_response.json()["timeout_seconds"] == 0.5

    clamped_timeout_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={
            "goal": "Clamp the timeout.",
            "toolsets": ["file"],
            "model": "product-echo/simple",
            "timeout_seconds": 5.0,
        },
    )
    assert clamped_timeout_response.status_code == 201
    assert clamped_timeout_response.json()["timeout_seconds"] == 2.0


def test_process_next_queued_run_marks_timeout_and_persists_terminal_summary(
    test_client: TestClient,
    monkeypatch,
) -> None:
    del test_client
    with get_db_session() as session:
        seed_default_data(session)
        parent = AgentOSService(session).create_session("Timeout Parent")
        service = SubagentDelegationService(session)
        spawn_response = service.spawn(
            parent_session_id=parent.id,
            payload=SubagentSpawnRequest(
                goal="Long running child",
                context="Keep running",
                toolsets=["file"],
                model="product-echo/simple",
                max_iterations=2,
            ),
        )
        child_id = spawn_response.child_session_id

    def _raise_timeout(*args, **kwargs):
        raise TimeoutError("delegated execution timed out")

    monkeypatch.setattr(
        "app.services.agent_execution.AgentExecutionService._execute_request",
        _raise_timeout,
    )

    with get_db_session() as session:
        service = SubagentDelegationService(session)
        processed = service.process_next_queued_run()
        assert processed is True

    with get_db_session() as session:
        run = session.exec(
            select(SessionSubagentRun).where(SessionSubagentRun.child_session_id == child_id)
        ).one()
        parent_messages = list(
            session.exec(
                select(Message)
                .where(Message.session_id == parent.id)
                .order_by(Message.sequence_number.asc())
            )
        )

    assert run.lifecycle_status == "timed_out"
    assert run.finished_at is not None
    assert run.error_code == "subagent_timed_out"
    assert run.error_summary is not None
    assert run.final_output_json is not None
    final_output = json.loads(run.final_output_json)
    assert final_output["status"] == "timed_out"
    assert "timed out" in final_output["summary"].lower()
    assert parent_messages
    assert "timed out" in parent_messages[-1].content_text.lower()


def test_concurrent_spawn_respects_active_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _isolated_backend(tmp_path, monkeypatch):
        with get_db_session() as session:
            parent = AgentOSService(session).create_session("Concurrent Spawn Parent")
            service = SubagentDelegationService(session)
            for index in range(2):
                service.spawn(
                    parent_session_id=parent.id,
                    payload=SubagentSpawnRequest(
                        goal=f"Queued child {index + 1}",
                        toolsets=["file"],
                        model="product-echo/simple",
                    ),
                )
            parent_id = parent.id

        barrier = threading.Barrier(3)
        results: list[str] = []
        errors: list[str] = []

        def _spawn_in_thread() -> None:
            with get_db_session() as session:
                service = SubagentDelegationService(session)
                barrier.wait()
                try:
                    response = service.spawn(
                        parent_session_id=parent_id,
                        payload=SubagentSpawnRequest(
                            goal="Competing spawn",
                            toolsets=["file"],
                            model="product-echo/simple",
                        ),
                    )
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    results.append(response.child_session_id)

        threads = [threading.Thread(target=_spawn_in_thread) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        with get_db_session() as session:
            repository = SubagentRepository(session)
            active_runs = repository.count_active_runs(parent_id)

        assert len(results) == 1
        assert len(errors) == 1
        assert "concurrency limit" in errors[0].lower()
        assert active_runs == 3


def test_claim_next_queued_run_is_atomic_under_basic_race(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _isolated_backend(tmp_path, monkeypatch):
        with get_db_session() as session:
            parent = AgentOSService(session).create_session("Claim Race Parent")
            service = SubagentDelegationService(session)
            spawn_response = service.spawn(
                parent_session_id=parent.id,
                payload=SubagentSpawnRequest(
                    goal="Claim me once",
                    toolsets=["file"],
                    model="product-echo/simple",
                ),
            )
            child_id = spawn_response.child_session_id

        barrier = threading.Barrier(3)
        claimed_ids: list[str | None] = []

        def _claim_in_thread() -> None:
            with get_db_session() as session:
                service = SubagentDelegationService(session)
                barrier.wait()
                claimed_run = service._claim_next_queued_run_immediate()
                claimed_ids.append(claimed_run.id if claimed_run is not None else None)

        threads = [threading.Thread(target=_claim_in_thread) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        with get_db_session() as session:
            run = session.exec(
                select(SessionSubagentRun).where(SessionSubagentRun.child_session_id == child_id)
            ).one()

        assert claimed_ids.count(run.id) == 1
        assert claimed_ids.count(None) == 1
        assert run.lifecycle_status == "running"
        assert run.started_at is not None


def test_cleanup_stuck_running_subagent_marks_timed_out_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _isolated_backend(tmp_path, monkeypatch):
        with get_db_session() as session:
            parent = AgentOSService(session).create_session("Stuck Timeout Parent")
            service = SubagentDelegationService(session)
            spawn_response = service.spawn(
                parent_session_id=parent.id,
                payload=SubagentSpawnRequest(
                    goal="Expire this run",
                    toolsets=["file"],
                    model="product-echo/simple",
                    timeout_seconds=0.2,
                ),
            )
            child_id = spawn_response.child_session_id
            parent_id = parent.id

        stale_started_at = datetime.now(UTC) - timedelta(seconds=5)
        with get_db_session() as session:
            run = SubagentDelegationService(session)._claim_next_queued_run_immediate()
            assert run is not None
            run.started_at = stale_started_at
            run.updated_at = stale_started_at
            session.add(run)
            session.commit()

        with get_db_session() as session:
            cleaned = SubagentDelegationService(session).cleanup_stuck_runs()
            assert cleaned == 1

        with get_db_session() as session:
            cleaned_again = SubagentDelegationService(session).cleanup_stuck_runs()
            run = session.exec(
                select(SessionSubagentRun).where(SessionSubagentRun.child_session_id == child_id)
            ).one()
            child = session.exec(select(SessionRecord).where(SessionRecord.id == child_id)).one()
            parent_messages = list(
                session.exec(
                    select(Message)
                    .where(Message.session_id == parent_id)
                    .order_by(Message.sequence_number.asc())
                )
            )

        assert cleaned_again == 0
        assert run.lifecycle_status == "timed_out"
        assert run.parent_summary_message_id is not None
        assert child.status == "timed_out"
        assert len(parent_messages) == 1
        assert "timed out" in parent_messages[0].content_text.lower()


def test_cleanup_stuck_running_subagent_with_cancel_request_marks_cancelled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _isolated_backend(tmp_path, monkeypatch):
        with get_db_session() as session:
            parent = AgentOSService(session).create_session("Stuck Cancel Parent")
            service = SubagentDelegationService(session)
            spawn_response = service.spawn(
                parent_session_id=parent.id,
                payload=SubagentSpawnRequest(
                    goal="Cancel this run",
                    toolsets=["file"],
                    model="product-echo/simple",
                    timeout_seconds=0.2,
                ),
            )
            child_id = spawn_response.child_session_id
            parent_id = parent.id

        stale_started_at = datetime.now(UTC) - timedelta(seconds=5)
        with get_db_session() as session:
            run = SubagentDelegationService(session)._claim_next_queued_run_immediate()
            assert run is not None
            run.started_at = stale_started_at
            run.updated_at = stale_started_at
            run.cancellation_requested_at = utc_now()
            session.add(run)
            session.commit()

        with get_db_session() as session:
            cleaned = SubagentDelegationService(session).cleanup_stuck_runs()
            assert cleaned == 1

        with get_db_session() as session:
            run = session.exec(
                select(SessionSubagentRun).where(SessionSubagentRun.child_session_id == child_id)
            ).one()
            parent_messages = list(
                session.exec(
                    select(Message)
                    .where(Message.session_id == parent_id)
                    .order_by(Message.sequence_number.asc())
                )
            )

        assert run.lifecycle_status == "cancelled"
        assert run.finished_at is not None
        assert parent_messages
        assert "interrupted" in parent_messages[-1].content_text.lower()


def test_running_subagent_honors_cooperative_cancel_before_persisting_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _isolated_backend(tmp_path, monkeypatch):
        with get_db_session() as session:
            parent = AgentOSService(session).create_session("Cooperative Cancel Parent")
            service = SubagentDelegationService(session)
            spawn_response = service.spawn(
                parent_session_id=parent.id,
                payload=SubagentSpawnRequest(
                    goal="Cancel during provider response",
                    toolsets=["file"],
                    model="product-echo/simple",
                    timeout_seconds=1.0,
                ),
            )
            child_id = spawn_response.child_session_id
            parent_id = parent.id

        async def _cancel_during_chat(self, messages, tools=None, model=None, **kwargs):
            del self, messages, tools, model, kwargs
            with get_db_session() as inner_session:
                run = inner_session.exec(
                    select(SessionSubagentRun).where(
                        SessionSubagentRun.child_session_id == child_id
                    )
                ).one()
                run.cancellation_requested_at = utc_now()
                inner_session.add(run)
                inner_session.commit()
            return LLMResponse(
                content="This output should not be committed to the child transcript.",
                finish_reason="stop",
                usage={},
            )

        monkeypatch.setattr(
            "app.adapters.kernel.nanobot.ProductEchoLLMProvider.chat",
            _cancel_during_chat,
        )

        with get_db_session() as session:
            processed = SubagentDelegationService(session).process_next_queued_run()
            assert processed is True

        with get_db_session() as session:
            run = session.exec(
                select(SessionSubagentRun).where(SessionSubagentRun.child_session_id == child_id)
            ).one()
            child_messages = list(
                session.exec(
                    select(Message)
                    .where(Message.session_id == child_id)
                    .order_by(Message.sequence_number.asc())
                )
            )
            parent_messages = list(
                session.exec(
                    select(Message)
                    .where(Message.session_id == parent_id)
                    .order_by(Message.sequence_number.asc())
                )
            )

        assert run.lifecycle_status == "cancelled"
        assert run.final_output_json is not None
        final_output = json.loads(run.final_output_json)
        assert final_output["status"] == "cancelled"
        assert child_messages == []
        assert parent_messages
        assert "interrupted" in parent_messages[-1].content_text.lower()
