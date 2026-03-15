from __future__ import annotations

import json
import platform
import time
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from nanobot.providers.base import LLMResponse, ToolCallRequest
from sqlalchemy import event, text
from sqlmodel import select

from alembic import command
from app.core.agent_profile_defaults import LEGACY_AGENT_PROFILE
from app.core.config import clear_settings_cache, get_settings
from app.core.secrets import clear_secret_store_cache
from app.db.seed import seed_default_data
from app.db.session import clear_engine_cache, get_db_session
from app.main import create_app
from app.models.entities import (
    Agent,
    AgentProfile,
    Approval,
    AuditEvent,
    CronJob,
    Message,
    SessionRecord,
    Setting,
    Task,
    TaskRun,
    ToolCall,
    ToolPermission,
    ToolPolicyOverride,
    utc_now,
)
from app.services.runtime_supervisor import RuntimeSupervisor


def _alembic_config() -> Config:
    settings = get_settings()
    config = Config(str(settings.backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(settings.backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


@contextmanager
def _token_protected_client(
    *,
    tmp_path: Path,
    monkeypatch,
    bootstrap_token: str,
    shutdown_callback=None,
    runtime_supervisor=None,
    use_default_runtime_supervisor: bool = False,
):
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
    monkeypatch.setenv("SUBAGENT_WORKER_POLL_INTERVAL_SECONDS", "0.1")
    monkeypatch.setenv("SUBAGENT_RUN_TIMEOUT_SECONDS", "1.0")
    monkeypatch.setenv("SUBAGENT_MAX_RUN_TIMEOUT_SECONDS", "2.0")
    monkeypatch.setenv("SUBAGENT_STUCK_GRACE_SECONDS", "0.1")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "1800")
    monkeypatch.setenv("STALE_TASK_RUN_SECONDS", "1")
    monkeypatch.setenv("APP_SECRET_BACKEND", "memory")
    monkeypatch.setenv("APP_BOOTSTRAP_TOKEN", bootstrap_token)

    clear_settings_cache()
    clear_secret_store_cache()
    clear_engine_cache()

    command.upgrade(_alembic_config(), "head")
    with get_db_session() as session:
        seed_default_data(session)

    try:
        app = (
            create_app(shutdown_callback=shutdown_callback)
            if use_default_runtime_supervisor
            else create_app(
                shutdown_callback=shutdown_callback,
                runtime_supervisor=runtime_supervisor or RuntimeSupervisor(get_settings()),
            )
        )
        with TestClient(app) as client:
            yield client
    finally:
        clear_engine_cache()
        clear_settings_cache()
        clear_secret_store_cache()


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


def _write_skill(
    root: Path,
    directory: str,
    *,
    name: str,
    description: str,
    metadata: str,
    body: str,
    enabled: str | None = None,
) -> Path:
    skill_dir = root / directory
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
    ]
    if enabled is not None:
        lines.append(f"enabled: {enabled}")
    lines.extend(
        [
            f"metadata: {metadata}",
            "---",
            body,
        ]
    )
    path = skill_dir / "SKILL.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_health_check_returns_ok_payload(test_client: TestClient) -> None:
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {
        "status": "ok",
        "service": "backend",
        "version": "0.1.0",
    }


def test_bootstrap_token_is_required_when_configured(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _token_protected_client(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        bootstrap_token="desktop-token",
    ) as client:
        health_without_token = client.get("/health")
        assert health_without_token.status_code == 401
        assert health_without_token.json()["detail"] == "Invalid bootstrap token."

        health_with_wrong_token = client.get(
            "/health",
            headers={"X-Backend-Bootstrap-Token": "wrong"},
        )
        assert health_with_wrong_token.status_code == 401

        health_with_token = client.get(
            "/health",
            headers={"X-Backend-Bootstrap-Token": "desktop-token"},
        )
        assert health_with_token.status_code == 200

        sessions_without_token = client.get("/sessions")
        assert sessions_without_token.status_code == 401

        sessions_with_token = client.get(
            "/sessions",
            headers={"X-Backend-Bootstrap-Token": "desktop-token"},
        )
        assert sessions_with_token.status_code == 200


def test_internal_shutdown_endpoint_invokes_shutdown_callback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls = {"count": 0}

    def shutdown_callback() -> None:
        calls["count"] += 1

    with _token_protected_client(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        bootstrap_token="desktop-token",
        shutdown_callback=shutdown_callback,
    ) as client:
        response = client.post(
            "/internal/shutdown",
            headers={"X-Backend-Bootstrap-Token": "desktop-token"},
        )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert calls["count"] == 1


class _HealthyRuntimeComponent:
    def __init__(self, _settings, *, probe):
        self.probe = probe

    def start(self) -> None:
        self.probe.mark_starting()
        self.probe.mark_tick_started()
        self.probe.mark_tick_succeeded()

    async def stop(self) -> None:
        self.probe.mark_stopped()


class _FailingRuntimeComponent:
    def __init__(self, _settings, *, probe):
        self.probe = probe

    def start(self) -> None:
        raise RuntimeError("runtime component failed to start")

    async def stop(self) -> None:
        self.probe.mark_stopped()


def test_operational_health_returns_ok_when_components_are_running(
    tmp_path: Path,
    monkeypatch,
) -> None:
    supervisor = RuntimeSupervisor(
        get_settings(),
        scheduler_factory=_HealthyRuntimeComponent,
        execution_worker_factory=_HealthyRuntimeComponent,
        subagent_worker_factory=_HealthyRuntimeComponent,
    )
    with _token_protected_client(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        bootstrap_token="desktop-token",
        runtime_supervisor=supervisor,
    ) as client:
        response = client.get(
            "/health/operational",
            headers={"X-Backend-Bootstrap-Token": "desktop-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["components"]["scheduler"]["status"] == "running"
    assert payload["components"]["execution_worker"]["status"] == "running"
    assert payload["components"]["subagent_worker"]["status"] == "running"
    assert payload["backlog"]["queued_subagents"] >= 0


def test_operational_health_returns_degraded_when_runtime_component_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    supervisor = RuntimeSupervisor(
        get_settings(),
        scheduler_factory=_FailingRuntimeComponent,
        execution_worker_factory=_HealthyRuntimeComponent,
        subagent_worker_factory=_HealthyRuntimeComponent,
    )
    with _token_protected_client(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        bootstrap_token="desktop-token",
        runtime_supervisor=supervisor,
    ) as client:
        response = client.get(
            "/health/operational",
            headers={"X-Backend-Bootstrap-Token": "desktop-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["components"]["scheduler"]["status"] == "degraded"
    assert "failed to start" in payload["components"]["scheduler"]["last_error_summary"]
    assert payload["components"]["execution_worker"]["status"] == "running"
    assert payload["components"]["subagent_worker"]["status"] == "running"


def test_operational_health_returns_degraded_when_execution_worker_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    supervisor = RuntimeSupervisor(
        get_settings(),
        scheduler_factory=_HealthyRuntimeComponent,
        execution_worker_factory=_FailingRuntimeComponent,
        subagent_worker_factory=_HealthyRuntimeComponent,
    )
    with _token_protected_client(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        bootstrap_token="desktop-token",
        runtime_supervisor=supervisor,
    ) as client:
        response = client.get(
            "/health/operational",
            headers={"X-Backend-Bootstrap-Token": "desktop-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["components"]["scheduler"]["status"] == "running"
    assert payload["components"]["execution_worker"]["status"] == "degraded"
    assert "failed to start" in payload["components"]["execution_worker"]["last_error_summary"]
    assert payload["components"]["subagent_worker"]["status"] == "running"


def test_create_app_uses_default_runtime_supervisor_when_not_injected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _token_protected_client(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        bootstrap_token="desktop-token",
        use_default_runtime_supervisor=True,
    ) as client:
        response = client.get(
            "/health/operational",
            headers={"X-Backend-Bootstrap-Token": "desktop-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["components"]["scheduler"]["status"] != "stopped"
    assert payload["components"]["execution_worker"]["status"] != "stopped"
    assert payload["components"]["subagent_worker"]["status"] != "stopped"


def test_get_agent_returns_seeded_default_agent(test_client: TestClient) -> None:
    response = test_client.get("/agent")

    assert response.status_code == 200
    payload = response.json()

    assert payload["slug"] == "main"
    assert payload["is_default"] is True
    assert payload["profile"]["display_name"] == "Nanobot"
    assert "complete work end-to-end" in payload["profile"]["identity_text"]
    assert payload["profile"]["user_context_text"] == ""
    assert "auditable product state" in payload["profile"]["policy_base_text"]


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


def test_skills_endpoint_lists_precedence_and_blocked_reasons(
    test_client: TestClient,
) -> None:
    workspace_root = Path(test_client.get("/settings/operational").json()["workspace_root"])
    fixture_root = workspace_root.parent
    bundled_root = fixture_root / "bundled-skills"
    user_root = fixture_root / ".forkclaw" / "skills"
    workspace_skills_root = workspace_root / "skills"

    _write_skill(
        bundled_root,
        "review",
        name="Code Review",
        description="Bundled",
        metadata='{"forkclaw":{"requires":{"tools":["read_file"]}}}',
        body="Bundled body",
    )
    _write_skill(
        user_root,
        "review",
        name="Code Review",
        description="User",
        metadata='{"forkclaw":{"requires":{"tools":["read_file"]}}}',
        body="User body",
    )
    _write_skill(
        workspace_skills_root,
        "review",
        name="Code Review",
        description="Workspace",
        metadata='{"forkclaw":{"requires":{"tools":["read_file"]}}}',
        body="Workspace body",
    )
    _write_skill(
        workspace_skills_root,
        "darwin-only",
        name="Darwin Helper",
        description="Only for macOS",
        metadata=json.dumps(
            {"forkclaw": {"os": ["windows" if platform.system().lower() != "windows" else "linux"]}}
        ),
        body="macOS only",
    )
    _write_skill(
        workspace_skills_root,
        "needs-env",
        name="Needs Env",
        description="Requires env",
        metadata='{"forkclaw":{"requires":{"env":["SPECIAL_TOKEN"]}}}',
        body="token required",
    )

    response = test_client.get("/skills")
    assert response.status_code == 200

    payload = response.json()
    items = {item["key"]: item for item in payload["items"]}

    assert payload["strategy"] == "all_eligible"
    assert items["code-review"]["origin"] == "workspace"
    assert items["code-review"]["selected"] is True
    assert items["darwin-helper"]["eligible"] is False
    assert items["darwin-helper"]["blocked_reasons"] == ["unsupported_os"]
    assert items["needs-env"]["eligible"] is False
    assert items["needs-env"]["blocked_reasons"] == ["missing_env"]


def test_updating_skill_config_redacts_secrets_and_enables_selection(
    test_client: TestClient,
) -> None:
    workspace_root = Path(test_client.get("/settings/operational").json()["workspace_root"])
    workspace_skills_root = workspace_root / "skills"
    _write_skill(
        workspace_skills_root,
        "special-helper",
        name="Special Helper",
        description="Needs a primary env",
        metadata='{"forkclaw":{"primaryEnv":"SPECIAL_TOKEN","requires":{"env":["SPECIAL_TOKEN"]}}}',
        body="Use SPECIAL_TOKEN if present.",
    )

    before = test_client.get("/skills")
    assert before.status_code == 200
    before_item = next(item for item in before.json()["items"] if item["key"] == "special-helper")
    assert before_item["selected"] is False
    assert before_item["blocked_reasons"] == ["missing_env"]

    update_response = test_client.put(
        "/skills/special-helper",
        json={
            "enabled": True,
            "config": {"mode": "strict"},
            "api_key": "super-secret",
        },
    )
    assert update_response.status_code == 200
    update_item = update_response.json()

    assert update_item["selected"] is True
    assert update_item["config"] == {"mode": "strict"}
    assert "super-secret" not in update_response.text

    settings_response = test_client.get("/settings")
    settings_items = settings_response.json()["items"]
    config_row = next(
        item
        for item in settings_items
        if item["scope"] == "skills.entries.special-helper" and item["key"] == "config"
    )
    env_keys_row = next(
        item
        for item in settings_items
        if item["scope"] == "skills.entries.special-helper" and item["key"] == "env_keys"
    )
    assert config_row["value_json"] == '{"mode":"strict"}'
    assert env_keys_row["value_json"] == '["SPECIAL_TOKEN"]'


def test_agent_execution_persists_resolved_skills_metadata_and_exposes_it(
    test_client: TestClient,
) -> None:
    workspace_root = Path(test_client.get("/settings/operational").json()["workspace_root"])
    workspace_skills_root = workspace_root / "skills"
    _write_skill(
        workspace_skills_root,
        "list-files-coach",
        name="List Files Coach",
        description="Guide filesystem listing",
        metadata='{"forkclaw":{"requires":{"tools":["list_files"]}}}',
        body="Prefer shallow listings first.",
    )

    permission_response = test_client.put(
        "/tools/permissions/list_files",
        json={"permission_level": "allow"},
    )
    assert permission_response.status_code == 200

    execute_response = test_client.post(
        "/agent/execute",
        json={"title": "Skill Session", "message": "tool:list_files path=."},
    )
    assert execute_response.status_code == 201
    task_run_id = execute_response.json()["task_run_id"]

    with get_db_session() as session:
        task_run = session.exec(select(TaskRun).where(TaskRun.id == task_run_id)).one()

    assert task_run.output_json is not None
    task_run_payload = json.loads(task_run.output_json)
    assert task_run_payload["skills"]["strategy"] == "all_eligible"
    assert task_run_payload["skills"]["items"][0]["key"] == "list-files-coach"

    tool_calls_response = test_client.get("/tools/calls")
    assert tool_calls_response.status_code == 200
    tool_call = tool_calls_response.json()["items"][0]
    assert tool_call["guided_by_skills"][0]["key"] == "list-files-coach"

    activity_response = test_client.get("/activity/timeline")
    assert activity_response.status_code == 200
    activity_item = next(
        item for item in activity_response.json()["items"] if item["task_run_id"] == task_run_id
    )
    assert activity_item["skill_strategy"] == "all_eligible"
    assert activity_item["resolved_skills"][0]["key"] == "list-files-coach"


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
            "heartbeat_interval_seconds": 1800,
            "api_key": "sk-test",
            "clear_api_key": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["model_name"] == "gpt-4o-mini"
    assert payload["workspace_root"] == str(new_workspace)
    assert payload["heartbeat_interval_seconds"] == 1800
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


def test_operational_settings_accepts_kimi_alias_and_persists_canonical_provider(
    test_client: TestClient,
) -> None:
    workspace_root = test_client.get("/settings/operational").json()["workspace_root"]

    response = test_client.put(
        "/settings/operational",
        json={
            "provider": "kimi-for-coding",
            "model_name": "k2p5",
            "workspace_root": workspace_root,
            "max_iterations_per_execution": 2,
            "daily_budget_usd": 10,
            "monthly_budget_usd": 200,
            "default_view": "chat",
            "activity_poll_seconds": 3,
            "heartbeat_interval_seconds": 1800,
            "api_key": "kimi-secret",
            "clear_api_key": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "kimi-coding"
    assert payload["model_name"] == "k2p5"
    assert payload["provider_api_key_configured"] is True

    with get_db_session() as session:
        profile = session.exec(select(AgentProfile)).one()
        provider_setting = session.exec(
            select(Setting.value_text).where(
                Setting.scope == "runtime",
                Setting.key == "default_model_provider",
            )
        ).one()

    assert profile.model_provider == "kimi-coding"
    assert provider_setting == "kimi-coding"


def test_operational_settings_read_normalizes_legacy_kimi_provider(
    test_client: TestClient,
) -> None:
    with get_db_session() as session:
        provider_setting = session.exec(
            select(Setting).where(
                Setting.scope == "runtime",
                Setting.key == "default_model_provider",
            )
        ).one()
        model_setting = session.exec(
            select(Setting).where(
                Setting.scope == "runtime",
                Setting.key == "default_model_name",
            )
        ).one()
        profile = session.exec(select(AgentProfile)).one()

        provider_setting.value_text = "kimi-for-coding"
        model_setting.value_text = ""
        profile.model_provider = "kimi-for-coding"
        profile.model_name = None
        session.add(provider_setting)
        session.add(model_setting)
        session.add(profile)
        session.commit()

    response = test_client.get("/settings/operational")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "kimi-coding"
    assert payload["model_name"] == "k2p5"
    assert payload["provider_api_key_configured"] is False


def test_operational_settings_accepts_canonical_kimi_provider(
    test_client: TestClient,
) -> None:
    workspace_root = test_client.get("/settings/operational").json()["workspace_root"]

    response = test_client.put(
        "/settings/operational",
        json={
            "provider": "kimi-coding",
            "model_name": "k2p5",
            "workspace_root": workspace_root,
            "max_iterations_per_execution": 2,
            "daily_budget_usd": 10,
            "monthly_budget_usd": 200,
            "default_view": "settings",
            "activity_poll_seconds": 4,
            "heartbeat_interval_seconds": 1200,
            "api_key": None,
            "clear_api_key": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "kimi-coding"
    assert payload["model_name"] == "k2p5"
    assert payload["heartbeat_interval_seconds"] == 1200


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
            "heartbeat_interval_seconds": 1800,
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
        task_run = session.exec(select(TaskRun).where(TaskRun.id == payload["task_run_id"])).one()
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
        "prompt_context.resolved",
        "skills.resolved",
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


def test_session_messages_support_optional_pagination(
    test_client: TestClient,
) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Paged Chat"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]

    for content in ["one", "two", "three"]:
        response = test_client.post(
            f"/sessions/{session_id}/messages",
            json={"content": content},
        )
        assert response.status_code == 201

    page_one = test_client.get(f"/sessions/{session_id}/messages?limit=2")
    assert page_one.status_code == 200
    first_payload = page_one.json()
    assert [item["sequence_number"] for item in first_payload["items"]] == [5, 6]
    assert first_payload["items"][0]["content_text"] == "three"
    assert first_payload["items"][1]["content_text"].endswith("Reply: three")
    assert first_payload["has_more"] is True
    assert first_payload["next_before_sequence"] == first_payload["items"][0]["sequence_number"]

    page_two = test_client.get(
        f"/sessions/{session_id}/messages",
        params={"limit": 2, "before_sequence": first_payload["next_before_sequence"]},
    )
    assert page_two.status_code == 200
    second_payload = page_two.json()
    assert [item["sequence_number"] for item in second_payload["items"]] == [3, 4]
    assert second_payload["has_more"] is True

    full_payload = test_client.get(f"/sessions/{session_id}/messages").json()
    assert "has_more" not in full_payload
    assert "next_before_sequence" not in full_payload


def test_session_reset_rotates_conversation_id_and_hides_old_messages(
    test_client: TestClient,
) -> None:
    create_session_response = test_client.post("/sessions", json={"title": "Resettable"})
    assert create_session_response.status_code == 201
    session_id = create_session_response.json()["id"]
    original_conversation_id = create_session_response.json()["conversation_id"]

    first_response = test_client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "message before reset"},
    )
    assert first_response.status_code == 201

    reset_response = test_client.post(f"/sessions/{session_id}/reset")
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()

    assert reset_payload["id"] == session_id
    assert reset_payload["conversation_id"] != original_conversation_id
    assert reset_payload["summary"] is None

    empty_messages = test_client.get(f"/sessions/{session_id}/messages")
    assert empty_messages.status_code == 200
    assert empty_messages.json()["items"] == []

    second_response = test_client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "message after reset"},
    )
    assert second_response.status_code == 201

    visible_messages = test_client.get(f"/sessions/{session_id}/messages")
    assert visible_messages.status_code == 200
    assert [item["content_text"] for item in visible_messages.json()["items"]] == [
        "message after reset",
        second_response.json()["output_text"],
    ]

    with get_db_session() as session:
        all_messages = list(
            session.exec(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence_number.asc())
            )
        )
        reset_event = session.exec(
            select(AuditEvent)
            .where(
                AuditEvent.event_type == "session.conversation.reset",
                AuditEvent.entity_id == session_id,
            )
            .order_by(AuditEvent.created_at.desc())
        ).first()

    assert len(all_messages) == 4
    assert {item.conversation_id for item in all_messages} == {
        original_conversation_id,
        reset_payload["conversation_id"],
    }
    assert reset_event is not None


def test_agent_config_can_be_updated_and_reset(test_client: TestClient) -> None:
    update_response = test_client.put(
        "/agent/config",
        json={
            "name": "Desk Operator",
            "description": "Configuration for a family-office style operator.",
            "identity_text": (
                "Act as a meticulous desktop operator with strong accounting discipline."
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
    assert "complete work end-to-end" in reset_payload["profile"]["identity_text"]
    assert reset_payload["profile"]["user_context_text"] == ""
    assert "auditable product state" in reset_payload["profile"]["policy_base_text"]


def test_seed_promotes_legacy_prompt_defaults_without_overwriting_custom_model(
    test_client: TestClient,
) -> None:
    with get_db_session() as session:
        agent = session.exec(select(Agent)).one()
        profile = session.exec(select(AgentProfile)).one()
        agent.name = LEGACY_AGENT_PROFILE.name
        agent.description = LEGACY_AGENT_PROFILE.description
        profile.display_name = LEGACY_AGENT_PROFILE.display_name
        profile.identity_text = LEGACY_AGENT_PROFILE.identity_text
        profile.soul_text = LEGACY_AGENT_PROFILE.soul_text
        profile.user_context_text = LEGACY_AGENT_PROFILE.user_context_text
        profile.policy_base_text = LEGACY_AGENT_PROFILE.policy_base_text
        profile.model_provider = "kimi-coding"
        profile.model_name = "K2p5"
        session.add(agent)
        session.add(profile)
        session.commit()

    with get_db_session() as session:
        seed_default_data(session)

    with get_db_session() as session:
        profile = session.exec(select(AgentProfile)).one()
        heartbeat_setting = session.exec(
            select(Setting).where(
                Setting.scope == "runtime",
                Setting.key == "heartbeat_interval_seconds",
            )
        ).one()

    assert "complete work end-to-end" in profile.identity_text
    assert profile.user_context_text == ""
    assert profile.model_provider == "kimi-coding"
    assert profile.model_name == "K2p5"
    assert heartbeat_setting.value_text == "1800"


def test_seed_preserves_custom_prompt_defaults(test_client: TestClient) -> None:
    with get_db_session() as session:
        profile = session.exec(select(AgentProfile)).one()
        profile.identity_text = "Custom operator identity."
        profile.soul_text = "Custom operator soul."
        profile.user_context_text = "Custom user context."
        profile.policy_base_text = "Custom policy base."
        session.add(profile)
        session.commit()

    with get_db_session() as session:
        seed_default_data(session)

    with get_db_session() as session:
        profile = session.exec(select(AgentProfile)).one()

    assert profile.identity_text == "Custom operator identity."
    assert profile.soul_text == "Custom operator soul."
    assert profile.user_context_text == "Custom user context."
    assert profile.policy_base_text == "Custom policy base."


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
        "web_search",
        "web_fetch",
    }

    update_response = test_client.put(
        "/tools/permissions/list_files",
        json={"permission_level": "allow"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["permission_level"] == "allow"


def test_tool_permissions_hide_legacy_tools_outside_catalog(test_client: TestClient) -> None:
    unknown_tool_name = "legacy_cancel_subagent"
    with get_db_session() as session:
        agent = session.exec(select(Agent).where(Agent.is_default.is_(True))).one()
        session.add(
            ToolPermission(
                agent_id=agent.id,
                tool_name=unknown_tool_name,
                workspace_path=None,
                permission_level="allow",
                approval_required=False,
                status="active",
            )
        )
        session.commit()

    response = test_client.get("/tools/permissions")
    assert response.status_code == 200
    tool_names = {item["tool_name"] for item in response.json()["items"]}
    assert unknown_tool_name not in tool_names


def test_tool_policy_hides_legacy_overrides_outside_catalog(test_client: TestClient) -> None:
    unknown_tool_name = "legacy_cancel_subagent"
    with get_db_session() as session:
        agent = session.exec(select(Agent).where(Agent.is_default.is_(True))).one()
        session.add(
            ToolPolicyOverride(
                agent_id=agent.id,
                tool_name=unknown_tool_name,
                permission_level="allow",
                status="active",
            )
        )
        session.commit()

    response = test_client.get("/tools/policy")
    assert response.status_code == 200
    override_tool_names = {item["tool_name"] for item in response.json()["overrides"]}
    assert unknown_tool_name not in override_tool_names


def test_agent_execution_ignores_legacy_permissions_outside_catalog(
    test_client: TestClient,
) -> None:
    unknown_tool_name = "legacy_cancel_subagent"
    with get_db_session() as session:
        agent = session.exec(select(Agent).where(Agent.is_default.is_(True))).one()
        session.add(
            ToolPermission(
                agent_id=agent.id,
                tool_name=unknown_tool_name,
                workspace_path=None,
                permission_level="allow",
                approval_required=False,
                status="active",
            )
        )
        session.commit()

    execute_response = test_client.post(
        "/agent/execute",
        json={"message": "ping from legacy residue"},
    )
    assert execute_response.status_code == 201
    payload = execute_response.json()
    assert payload["status"] == "completed"
    assert "Reply: ping from legacy residue" in payload["output_text"]

    with get_db_session() as session:
        audit_event = session.exec(
            select(AuditEvent)
            .where(
                AuditEvent.event_type == "tool_permissions.legacy_ignored",
                AuditEvent.entity_id == payload["task_run_id"],
            )
            .order_by(AuditEvent.created_at.desc())
        ).first()

    assert audit_event is not None
    assert unknown_tool_name in (audit_event.payload_json or "")


def test_tool_catalog_and_policy_are_exposed_from_the_backend(test_client: TestClient) -> None:
    catalog_response = test_client.get("/tools/catalog")
    assert catalog_response.status_code == 200
    catalog_payload = catalog_response.json()

    assert "items" in catalog_payload
    items = catalog_payload["items"]
    assert len(items) > 0

    # Verify all expected fields from ToolCatalogEntryRead are present
    first_item = items[0]
    expected_keys = {
        "id",
        "label",
        "description",
        "group",
        "group_label",
        "risk",
        "status",
        "input_schema",
        "output_schema",
        "requires_workspace",
    }
    assert expected_keys.issubset(first_item.keys())

    # Ensure properties are properly populated
    assert isinstance(first_item["id"], str)
    assert isinstance(first_item["label"], str)
    assert isinstance(first_item["description"], str)
    assert isinstance(first_item["group"], str)
    assert isinstance(first_item["group_label"], str)
    assert isinstance(first_item["risk"], str)
    assert isinstance(first_item["status"], str)
    assert isinstance(first_item["input_schema"], dict)
    assert isinstance(first_item["requires_workspace"], bool)

    by_id = {item["id"]: item for item in items}
    assert by_id["list_files"]["group"] == "group:fs"
    assert by_id["web_search"]["group"] == "group:web"
    assert by_id["web_search"]["status"] == "experimental"
    assert by_id["web_fetch"]["label"] == "Web fetch"

    policy_response = test_client.get("/tools/policy")
    assert policy_response.status_code == 200
    policy_payload = policy_response.json()

    assert policy_payload["profile_id"] == "minimal"
    assert [item["id"] for item in policy_payload["profiles"]] == [
        "minimal",
        "coding",
        "research",
        "full",
    ]
    assert policy_payload["profiles"][0]["defaults"]["group:web"] == "deny"


def test_tool_policy_profile_change_recomputes_effective_permissions(
    test_client: TestClient,
) -> None:
    update_response = test_client.put("/tools/policy", json={"profile_id": "research"})
    assert update_response.status_code == 200
    assert update_response.json()["profile_id"] == "research"

    permissions_response = test_client.get("/tools/permissions")
    assert permissions_response.status_code == 200
    permissions = {
        item["tool_name"]: item["permission_level"] for item in permissions_response.json()["items"]
    }
    assert permissions["web_search"] == "allow"
    assert permissions["web_fetch"] == "allow"
    assert permissions["list_files"] == "ask"


def test_tool_permission_override_is_reflected_in_policy_state(test_client: TestClient) -> None:
    profile_response = test_client.put("/tools/policy", json={"profile_id": "research"})
    assert profile_response.status_code == 200

    override_response = test_client.put(
        "/tools/permissions/web_fetch",
        json={"permission_level": "ask"},
    )
    assert override_response.status_code == 200
    assert override_response.json()["permission_level"] == "ask"

    policy_response = test_client.get("/tools/policy")
    assert policy_response.status_code == 200
    overrides = {
        item["tool_name"]: item["permission_level"] for item in policy_response.json()["overrides"]
    }
    assert overrides["web_fetch"] == "ask"


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
        task_run = session.exec(select(TaskRun).where(TaskRun.id == payload["task_run_id"])).one()
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
        refreshed_approval = session.exec(select(Approval).where(Approval.id == approval.id)).one()
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
        refreshed_approval = session.exec(select(Approval).where(Approval.id == approval.id)).one()
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
    tool_entry = next(entry for entry in item["entries"] if entry["type"] == "tool_call")
    assert tool_entry["metadata"] == {"tool_name": "list_files"}


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


def test_shell_exec_defaults_to_ask_and_includes_resolved_cwd_in_approval(
    test_client: TestClient,
) -> None:
    execute_response = test_client.post(
        "/agent/execute",
        json={
            "title": "Shell Approval Session",
            "message": "tool:shell_exec command='pwd' cwd=.",
        },
    )
    assert execute_response.status_code == 201
    payload = execute_response.json()

    assert payload["status"] == "awaiting_approval"

    approvals_response = test_client.get("/approvals")
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()["items"]
    approval_item = next(item for item in approvals if item["tool_name"] == "shell_exec")

    workspace_root = test_client.get("/tools/permissions").json()["workspace_root"]
    assert workspace_root in approval_item["requested_action"]
    assert '"command": "pwd"' in (approval_item["tool_input_json"] or "")


def test_shell_exec_persists_structured_output_payload(test_client: TestClient) -> None:
    permission_response = test_client.put(
        "/tools/permissions/shell_exec",
        json={"permission_level": "allow"},
    )
    assert permission_response.status_code == 200

    execute_response = test_client.post(
        "/agent/execute",
        json={
            "title": "Shell Persisted Output Session",
            "message": "tool:shell_exec command='echo hello' cwd=.",
        },
    )
    assert execute_response.status_code == 201
    payload = execute_response.json()

    assert payload["status"] == "completed"
    assert "shell_exec" in payload["tools_used"]

    with get_db_session() as session:
        tool_call = session.exec(
            select(ToolCall)
            .where(ToolCall.tool_name == "shell_exec")
            .order_by(ToolCall.created_at.desc())
        ).one()

    output_payload = json.loads(tool_call.output_json or "{}")
    assert output_payload["data"]["stdout"] == "hello\n"
    assert output_payload["data"]["stderr"] == ""
    assert output_payload["data"]["exit_code"] == 0
    assert output_payload["data"]["cwd_resolved"].endswith("/workspace")
    assert output_payload["data"]["truncated"] is False


def test_shell_exec_activity_timeline_includes_runtime_events(test_client: TestClient) -> None:
    permission_response = test_client.put(
        "/tools/permissions/shell_exec",
        json={"permission_level": "allow"},
    )
    assert permission_response.status_code == 200

    execute_response = test_client.post(
        "/agent/execute",
        json={
            "title": "Shell Timeline Session",
            "message": "tool:shell_exec command='pwd' cwd=.",
        },
    )
    assert execute_response.status_code == 201

    response = test_client.get("/activity/timeline")
    assert response.status_code == 200
    item = next(
        current
        for current in response.json()["items"]
        if current["session_title"] == "Shell Timeline Session"
    )

    audit_event_types = {entry["event_type"] for entry in item["audit_log"]}
    assert {"tool.started", "tool.completed"} <= audit_event_types

    audit_titles = {entry["title"] for entry in item["entries"] if entry["type"] == "audit"}
    assert {"tool.started", "tool.completed"} <= audit_titles


def test_activity_timeline_supports_optional_cursor_pagination(
    test_client: TestClient,
) -> None:
    for index in range(3):
        response = test_client.post(
            "/agent/execute",
            json={"title": f"Cursor Session {index}", "message": f"hello {index}"},
        )
        assert response.status_code == 201

    first_page = test_client.get("/activity/timeline?limit=2")
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert len(first_payload["items"]) == 2
    assert first_payload["next_cursor"] is not None

    second_page = test_client.get(
        "/activity/timeline",
        params={"limit": 2, "cursor": first_payload["next_cursor"]},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert len(second_payload["items"]) >= 1
    assert {item["task_run_id"] for item in first_payload["items"]}.isdisjoint(
        {item["task_run_id"] for item in second_payload["items"]}
    )


def test_activity_timeline_query_budget_is_batched(
    test_client: TestClient,
) -> None:
    for index in range(5):
        response = test_client.post(
            "/agent/execute",
            json={"title": f"Budget Session {index}", "message": "tool:list_files path=."},
        )
        assert response.status_code == 201

    statements: list[str] = []

    def before_cursor_execute(_conn, _cursor, statement, _params, _context, _executemany):
        statements.append(statement)

    from app.db.session import get_engine

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        response = test_client.get("/activity/timeline?limit=5")
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 5
    assert len(statements) <= 11


def test_cron_jobs_dashboard_empty(test_client: TestClient) -> None:
    response = test_client.get("/cron-jobs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 0
    assert isinstance(data["history"], list)
    assert "heartbeat" in data


def test_cron_jobs_dashboard_populated(test_client: TestClient) -> None:
    # Create a job first
    create_response = test_client.post(
        "/cron-jobs",
        json={
            "name": "Dashboard Test Job",
            "schedule": "every:5m",
            "payload": {"job_type": "review_pending_approvals"},
        },
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    # Verify the dashboard returns the created job
    response = test_client.get("/cron-jobs")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 1

    # Check if the created job is in the items
    dashboard_job = next((item for item in data["items"] if item["id"] == job_id), None)
    assert dashboard_job is not None
    assert dashboard_job["name"] == "Dashboard Test Job"
    assert dashboard_job["schedule"] == "every:5m"
    assert dashboard_job["payload"]["job_type"] == "review_pending_approvals"

    # Cleanup
    test_client.delete(f"/cron-jobs/{job_id}")


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
        lambda: (
            [
                item
                for item in test_client.get("/cron-jobs").json()["history"]
                if item["cron_job_id"] == job["id"] and item["status"] == "completed"
            ]
            or None
        ),
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
        heartbeat_setting = session.exec(
            select(Setting).where(
                Setting.scope == "runtime",
                Setting.key == "heartbeat_interval_seconds",
            )
        ).one()
        heartbeat_setting.value_text = "0.4"
        session.add(heartbeat_setting)
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
            lambda current: (
                current
                if current["heartbeat"]["last_run_at"] is not None
                and current["heartbeat"]["cleaned_stale_runs"] >= 1
                else None
            )
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


def test_subagent_spawn_persists_child_session_and_lifecycle(
    test_client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.subagents.SubagentDelegationService.process_next_queued_run",
        lambda self: False,
    )
    parent_response = test_client.post("/sessions", json={"title": "Parent Session"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    with get_db_session() as session:
        parent_session = session.exec(
            select(SessionRecord).where(SessionRecord.id == parent_id)
        ).one()
        parent_message = Message(
            session_id=parent_id,
            conversation_id=parent_session.conversation_id,
            role="user",
            status="committed",
            sequence_number=1,
            content_text="Please audit the workspace for stale files.",
        )
        parent_task = Task(
            agent_id=session.exec(select(Agent.id).where(Agent.is_default.is_(True))).one(),
            session_id=parent_id,
            title="Parent orchestration",
            kind="agent_execution",
            status="running",
            payload_json=json.dumps({"message": parent_message.content_text}),
        )
        session.add(parent_message)
        session.flush()
        session.add(parent_task)
        session.flush()
        parent_task_run = TaskRun(
            task_id=parent_task.id,
            status="running",
            attempt=1,
            started_at=utc_now(),
        )
        session.add(parent_task_run)
        session.commit()
        parent_message_id = parent_message.id
        parent_task_run_id = parent_task_run.id

    spawn_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={
            "goal": "Audit the workspace for stale files",
            "context": "Focus on build artifacts only.",
            "toolsets": ["group:fs", "group:web"],
            "model": "product-echo/simple",
            "max_iterations": 20,
            "launcher_message_id": parent_message_id,
            "launcher_task_run_id": parent_task_run_id,
        },
    )

    assert spawn_response.status_code == 201
    payload = spawn_response.json()
    child_id = payload["child_session_id"]

    assert payload == {
        "parent_session_id": parent_id,
        "child_session_id": child_id,
        "status": "accepted",
        "runtime": "subagent",
        "spawn_depth": 1,
        "toolsets": ["file", "web"],
        "model": "product-echo/simple",
        "max_iterations": 20,
        "timeout_seconds": 1.0,
    }

    with get_db_session() as session:
        child_row = (
            session.connection()
            .execute(
                text(
                    """
                SELECT kind, parent_session_id, root_session_id, spawn_depth,
                       delegated_goal, delegated_context_snapshot, tool_profile,
                       model_override, max_iterations, timeout_seconds
                FROM sessions
                WHERE id = :child_id
                """
                ),
                {"child_id": child_id},
            )
            .mappings()
            .one()
        )
        run_row = (
            session.connection()
            .execute(
                text(
                    """
                SELECT launcher_session_id, child_session_id, launcher_message_id,
                       launcher_task_run_id, parent_summary_message_id,
                       lifecycle_status, cancellation_requested_at, final_summary, final_output_json
                FROM session_subagent_runs
                WHERE child_session_id = :child_id
                """
                ),
                {"child_id": child_id},
            )
            .mappings()
            .one()
        )

    assert child_row["kind"] == "subagent"
    assert child_row["parent_session_id"] == parent_id
    assert child_row["root_session_id"] == parent_id
    assert child_row["spawn_depth"] == 1
    assert child_row["delegated_goal"] == "Audit the workspace for stale files"
    assert "Focus on build artifacts only." in child_row["delegated_context_snapshot"]
    assert "Parent snapshot:" in child_row["delegated_context_snapshot"]
    assert json.loads(child_row["tool_profile"]) == ["file", "web"]
    assert child_row["model_override"] == "product-echo/simple"
    assert child_row["max_iterations"] == 20
    assert child_row["timeout_seconds"] == 1.0
    assert run_row["launcher_session_id"] == parent_id
    assert run_row["child_session_id"] == child_id
    assert run_row["launcher_message_id"] == parent_message_id
    assert run_row["launcher_task_run_id"] == parent_task_run_id
    assert run_row["parent_summary_message_id"] is None
    assert run_row["lifecycle_status"] == "queued"
    assert run_row["cancellation_requested_at"] is None
    assert run_row["final_summary"] is None
    assert run_row["final_output_json"] is None

    fallback_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={
            "goal": "Fallback anchor",
            "toolsets": ["group:fs"],
        },
    )
    assert fallback_response.status_code == 201
    fallback_child_id = fallback_response.json()["child_session_id"]

    with get_db_session() as session:
        fallback_run = (
            session.connection()
            .execute(
                text(
                    """
                SELECT launcher_message_id, launcher_task_run_id
                FROM session_subagent_runs
                WHERE child_session_id = :child_id
                """
                ),
                {"child_id": fallback_child_id},
            )
            .mappings()
            .one()
        )

    assert fallback_run["launcher_message_id"] == parent_message_id
    assert fallback_run["launcher_task_run_id"] is None

    list_response = test_client.get(f"/sessions/{parent_id}/subagents")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload["items"]) == 2
    items_by_id = {item["id"]: item for item in list_payload["items"]}
    assert set(items_by_id) == {child_id, fallback_child_id}
    assert items_by_id[child_id]["kind"] == "subagent"
    assert items_by_id[child_id]["timeout_seconds"] == 1.0
    assert items_by_id[child_id]["run"]["lifecycle_status"] == "queued"
    assert items_by_id[fallback_child_id]["run"]["launcher_message_id"] == parent_message_id
    assert items_by_id[fallback_child_id]["run"].get("launcher_task_run_id") is None

    detail_response = test_client.get(f"/sessions/{parent_id}/subagents/{child_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["id"] == child_id
    assert detail_payload["delegated_goal"] == "Audit the workspace for stale files"
    assert detail_payload["timeout_seconds"] == 1.0
    assert detail_payload["run"]["lifecycle_status"] == "queued"
    assert len(detail_payload["timeline_events"]) == 1
    assert detail_payload["timeline_events"][0]["event_type"] == "subagent.spawned"
    assert detail_payload["timeline_events"][0]["status"] == "queued"
    assert "task_run_id" not in detail_payload["timeline_events"][0]
    assert "estimated_cost_usd" not in detail_payload["timeline_events"][0]


def test_acp_bridge_status_can_be_toggled(test_client: TestClient) -> None:
    initial = test_client.get("/acp/status")
    assert initial.status_code == 200
    assert initial.json()["enabled"] is False

    enabled = test_client.put("/acp/status", json={"enabled": True})
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True

    current = test_client.get("/acp/status")
    assert current.status_code == 200
    assert current.json()["enabled"] is True

    disabled = test_client.put("/acp/status", json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


def test_acp_session_endpoints_require_enabled_bridge(test_client: TestClient) -> None:
    create_response = test_client.post("/acp/sessions", json={"label": "ACP Off"})

    assert create_response.status_code == 400
    assert "disabled" in create_response.json()["detail"].lower()


def test_acp_session_endpoints_work_when_bridge_is_enabled(test_client: TestClient) -> None:
    enable_response = test_client.put("/acp/status", json={"enabled": True})
    assert enable_response.status_code == 200
    assert enable_response.json()["enabled"] is True

    create_response = test_client.post("/acp/sessions", json={"label": "ACP Smoke"})
    assert create_response.status_code == 200
    session_key = create_response.json()["session_key"]

    prompt_response = test_client.post(
        "/acp/prompt",
        json={"session_key": session_key, "text": "Ping ACP."},
    )
    assert prompt_response.status_code == 200
    prompt_payload = prompt_response.json()
    assert prompt_payload["session_key"] == session_key
    assert prompt_payload["output_text"]

    load_response = test_client.post(
        "/acp/load_session",
        json={"session_key": session_key, "limit": 20},
    )
    assert load_response.status_code == 200
    assert len(load_response.json()["messages"]) >= 2

    cancel_response = test_client.post("/acp/cancel", json={"session_key": session_key})
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_acp_create_session_invalid_parent(test_client: TestClient) -> None:
    test_client.put("/acp/status", json={"enabled": True})
    response = test_client.post("/acp/sessions", json={
        "label": "Invalid Parent",
        "parent_session_id": "non_existent_id"
    })
    assert response.status_code == 404
    assert "invalid parent_session_id" in response.json()["detail"].lower()


def test_subagent_runtime_acp_requires_enabled_bridge(test_client: TestClient) -> None:
    parent_response = test_client.post("/sessions", json={"title": "Parent Session"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    spawn_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "ACP runtime check", "runtime": "acp"},
    )

    assert spawn_response.status_code == 400
    assert "disabled" in spawn_response.json()["detail"].lower()


def test_sessions_listing_stays_main_only_and_can_include_subagent_counts(
    test_client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.subagents.SubagentDelegationService.process_next_queued_run",
        lambda self: False,
    )
    parent_response = test_client.post("/sessions", json={"title": "Visible Parent"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    spawn_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "Inspect files", "toolsets": ["group:fs"]},
    )
    assert spawn_response.status_code == 201
    child_id = spawn_response.json()["child_session_id"]

    sessions_response = test_client.get("/sessions")
    assert sessions_response.status_code == 200
    items = sessions_response.json()["items"]
    assert [item["id"] for item in items] == [parent_id]
    assert "subagent_counts" not in items[0]

    counted_response = test_client.get("/sessions?include_subagent_counts=true")
    assert counted_response.status_code == 200
    counted_item = counted_response.json()["items"][0]
    assert counted_item["id"] == parent_id
    assert counted_item["subagent_counts"] == {
        "total": 1,
        "queued": 1,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "timed_out": 0,
    }

    hidden_response = test_client.get(f"/sessions/{child_id}")
    assert hidden_response.status_code == 404


def test_subagent_cancel_is_idempotent_and_child_cannot_receive_user_messages(
    test_client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.subagents.SubagentDelegationService.process_next_queued_run",
        lambda self: False,
    )
    parent_response = test_client.post("/sessions", json={"title": "Parent"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    spawn_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "Summarize docs", "toolsets": ["group:fs"]},
    )
    assert spawn_response.status_code == 201
    child_id = spawn_response.json()["child_session_id"]

    first_cancel = test_client.post(f"/sessions/{parent_id}/subagents/{child_id}/cancel")
    assert first_cancel.status_code == 200
    assert first_cancel.json()["lifecycle_status"] == "cancelled"

    second_cancel = test_client.post(f"/sessions/{parent_id}/subagents/{child_id}/cancel")
    assert second_cancel.status_code == 200
    assert second_cancel.json()["lifecycle_status"] == "cancelled"

    message_response = test_client.post(
        f"/sessions/{child_id}/messages",
        json={"content": "hello child"},
    )
    assert message_response.status_code == 400
    assert "subagent" in message_response.json()["detail"].lower()


def test_subagent_spawn_validates_parent_kind_toolsets_and_concurrency(
    test_client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.subagents.SubagentDelegationService.process_next_queued_run",
        lambda self: False,
    )
    missing_parent = test_client.post(
        "/sessions/missing/subagents",
        json={"goal": "Do work", "toolsets": ["group:fs"]},
    )
    assert missing_parent.status_code == 404

    parent_response = test_client.post("/sessions", json={"title": "Parent"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    invalid_toolset = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "Do work", "toolsets": ["unknown-group"]},
    )
    assert invalid_toolset.status_code == 400
    assert "supported toolsets" in invalid_toolset.json()["detail"].lower()

    invalid_legacy_toolset = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "Do work", "toolsets": ["default"]},
    )
    assert invalid_legacy_toolset.status_code == 400
    assert "supported toolsets" in invalid_legacy_toolset.json()["detail"].lower()

    blank_goal = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "   ", "toolsets": ["group:fs"]},
    )
    assert blank_goal.status_code == 422
    assert test_client.get(f"/sessions/{parent_id}/subagents").json()["items"] == []

    child_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "Child", "toolsets": ["group:fs"]},
    )
    assert child_response.status_code == 201
    child_id = child_response.json()["child_session_id"]

    nested_spawn = test_client.post(
        f"/sessions/{child_id}/subagents",
        json={"goal": "Nested", "toolsets": ["group:fs"]},
    )
    assert nested_spawn.status_code == 400

    second_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "Second", "toolsets": ["group:fs"]},
    )
    third_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "Third", "toolsets": ["group:fs"]},
    )
    assert second_response.status_code == 201
    assert third_response.status_code == 201

    fourth_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={"goal": "Fourth", "toolsets": ["group:fs"]},
    )
    assert fourth_response.status_code == 400
    assert "concurrency" in fourth_response.json()["detail"].lower()


def test_subagent_with_empty_effective_scope_does_not_inherit_parent_tools(
    test_client: TestClient,
    monkeypatch,
) -> None:
    async def _request_list_files(self, messages, tools=None, model=None, **kwargs):
        del self, messages, tools, model, kwargs
        return LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call-list-files",
                    name="list_files",
                    arguments={"path": "."},
                )
            ],
            finish_reason="tool_calls",
            usage={},
        )

    monkeypatch.setattr(
        "app.adapters.kernel.nanobot.ProductEchoLLMProvider.chat",
        _request_list_files,
    )

    parent_response = test_client.post("/sessions", json={"title": "Scope Parent"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    spawn_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={
            "goal": "Attempt a terminal tool outside delegated scope.",
            "toolsets": ["group:runtime"],
            "model": "product-echo/simple",
        },
    )
    assert spawn_response.status_code == 201
    child_id = spawn_response.json()["child_session_id"]

    detail_payload = _wait_for(
        lambda: (
            lambda payload: (
                payload if payload["run"]["lifecycle_status"] in {"failed", "completed"} else None
            )
        )(test_client.get(f"/sessions/{parent_id}/subagents/{child_id}").json()),
        timeout=3.0,
        interval=0.1,
    )

    assert detail_payload["run"]["lifecycle_status"] == "completed"

    with get_db_session() as session:
        tool_call = session.exec(
            select(ToolCall)
            .where(ToolCall.session_id == child_id)
            .order_by(ToolCall.created_at.desc())
        ).first()

    assert tool_call is not None
    assert tool_call.tool_name == "list_files"
    assert tool_call.status == "denied"
    assert tool_call.output_json is not None
    assert "outside the delegated scope" in tool_call.output_json


def test_subagent_detail_and_cancel_require_matching_parent_session(
    test_client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.subagents.SubagentDelegationService.process_next_queued_run",
        lambda self: False,
    )
    first_parent = test_client.post("/sessions", json={"title": "First"})
    second_parent = test_client.post("/sessions", json={"title": "Second"})
    assert first_parent.status_code == 201
    assert second_parent.status_code == 201

    first_parent_id = first_parent.json()["id"]
    second_parent_id = second_parent.json()["id"]

    spawn_response = test_client.post(
        f"/sessions/{first_parent_id}/subagents",
        json={"goal": "Check scope", "toolsets": ["group:fs"]},
    )
    assert spawn_response.status_code == 201
    child_id = spawn_response.json()["child_session_id"]

    wrong_detail = test_client.get(f"/sessions/{second_parent_id}/subagents/{child_id}")
    assert wrong_detail.status_code == 404

    wrong_cancel = test_client.post(f"/sessions/{second_parent_id}/subagents/{child_id}/cancel")
    assert wrong_cancel.status_code == 404


def test_activity_timeline_includes_sanitized_subagent_lineage(test_client: TestClient) -> None:
    parent_response = test_client.post("/sessions", json={"title": "Timeline Parent"})
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]

    spawn_response = test_client.post(
        f"/sessions/{parent_id}/subagents",
        json={
            "goal": "Inspect the workspace and produce a short summary.",
            "context": "Focus on the top-level notes file.",
            "toolsets": ["group:fs"],
            "model": "product-echo/simple",
            "max_iterations": 2,
        },
    )
    assert spawn_response.status_code == 201
    child_id = spawn_response.json()["child_session_id"]

    def _find_subagent_item():
        response = test_client.get("/activity/timeline")
        assert response.status_code == 200
        for item in response.json()["items"]:
            if item["task_kind"] == "subagent_execution" and item["session_id"] == child_id:
                return item
        return None

    item = _wait_for(_find_subagent_item, timeout=3.0)
    assert item is not None
    assert item["lineage"] == {
        "parent_session_id": parent_id,
        "parent_session_title": "Timeline Parent",
        "child_session_id": child_id,
        "child_session_title": item["session_title"],
        "goal_summary": "Inspect the workspace and produce a short summary.",
        "status": item["status"],
        "task_run_id": item["task_run_id"],
        "estimated_cost_usd": item["estimated_cost_usd"],
    }
    assert all(
        audit_event.get("payload_json") is None
        for audit_event in item["audit_log"]
        if audit_event["event_type"].startswith("subagent")
    )
    assert any(
        entry["summary"] == "Inspect the workspace and produce a short summary."
        for entry in item["entries"]
        if entry["type"] == "audit"
    )
