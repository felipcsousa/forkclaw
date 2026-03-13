from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from app.core.config import clear_settings_cache
from app.db.session import get_engine


def test_schema_and_migrations_create_required_tables(test_client) -> None:
    del test_client
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())

    assert tables >= {
        "agents",
        "agent_profiles",
        "sessions",
        "session_subagent_runs",
        "memory_entries",
        "memory_relations",
        "memory_recall_log",
        "session_summaries",
        "memory_change_log",
        "messages",
        "tasks",
        "task_runs",
        "tool_permissions",
        "tool_calls",
        "cron_jobs",
        "memories",
        "documents",
        "approvals",
        "audit_events",
        "settings",
        "tool_policy_overrides",
        "tool_cache_entries",
    }

    task_runs_columns = {column["name"] for column in inspector.get_columns("task_runs")}
    audit_events_columns = {column["name"] for column in inspector.get_columns("audit_events")}
    tool_cache_columns = {column["name"] for column in inspector.get_columns("tool_cache_entries")}
    session_columns = {column["name"] for column in inspector.get_columns("sessions")}
    subagent_run_columns = {
        column["name"] for column in inspector.get_columns("session_subagent_runs")
    }
    memory_entry_columns = {column["name"] for column in inspector.get_columns("memory_entries")}
    memory_relation_columns = {
        column["name"] for column in inspector.get_columns("memory_relations")
    }
    memory_recall_columns = {
        column["name"] for column in inspector.get_columns("memory_recall_log")
    }
    session_summary_columns = {
        column["name"] for column in inspector.get_columns("session_summaries")
    }
    memory_change_columns = {
        column["name"] for column in inspector.get_columns("memory_change_log")
    }

    assert {"duration_ms", "estimated_cost_usd"} <= task_runs_columns
    assert {"level", "summary_text"} <= audit_events_columns
    assert {"tool_name", "cache_key", "value_json", "expires_at"} <= tool_cache_columns
    assert {
        "kind",
        "parent_session_id",
        "root_session_id",
        "spawn_depth",
        "delegated_goal",
        "delegated_context_snapshot",
        "tool_profile",
        "model_override",
        "max_iterations",
        "timeout_seconds",
    } <= session_columns
    assert {
        "launcher_session_id",
        "child_session_id",
        "launcher_message_id",
        "launcher_task_run_id",
        "task_id",
        "task_run_id",
        "parent_summary_message_id",
        "lifecycle_status",
        "started_at",
        "finished_at",
        "cancellation_requested_at",
        "final_summary",
        "final_output_json",
        "estimated_cost_usd",
        "error_code",
        "error_summary",
    } <= subagent_run_columns
    assert {
        "scope_type",
        "scope_key",
        "conversation_id",
        "session_id",
        "parent_session_id",
        "source_kind",
        "lifecycle_state",
        "title",
        "body",
        "summary",
        "importance",
        "confidence",
        "dedupe_hash",
        "created_by",
        "updated_by",
        "expires_at",
        "redaction_state",
        "security_state",
        "hidden_from_recall",
        "deleted_at",
    } <= memory_entry_columns
    assert {
        "from_memory_id",
        "to_memory_id",
        "relation_kind",
        "created_by",
    } <= memory_relation_columns
    assert {
        "memory_id",
        "scope_type",
        "scope_key",
        "conversation_id",
        "session_id",
        "run_id",
        "recall_reason",
        "decision",
        "rank",
    } <= memory_recall_columns
    assert {
        "scope_key",
        "session_id",
        "conversation_id",
        "parent_session_id",
        "task_run_id",
        "source_kind",
        "summary_text",
        "created_by",
    } <= session_summary_columns
    assert {
        "memory_id",
        "action",
        "actor_type",
        "actor_id",
        "before_snapshot",
        "after_snapshot",
    } <= memory_change_columns

    session_indexes = {index["name"] for index in inspector.get_indexes("sessions")}
    subagent_run_indexes = {
        index["name"] for index in inspector.get_indexes("session_subagent_runs")
    }
    memory_entry_indexes = {index["name"] for index in inspector.get_indexes("memory_entries")}
    memory_change_indexes = {index["name"] for index in inspector.get_indexes("memory_change_log")}

    assert {
        "ix_sessions_parent_session_id",
        "ix_sessions_root_session_id",
        "ix_sessions_kind",
    } <= session_indexes
    assert {
        "ix_session_subagent_runs_lifecycle_status",
        "ix_session_subagent_runs_launcher_session_id",
        "ix_session_subagent_runs_child_session_id",
    } <= subagent_run_indexes
    assert {
        "ix_memory_entries_scope_type_scope_key",
        "ix_memory_entries_dedupe_hash",
        "ix_memory_entries_conversation_id",
        "ix_memory_entries_session_id",
        "ix_memory_entries_parent_session_id",
        "ix_memory_entries_source_kind",
        "ix_memory_entries_lifecycle_state",
        "ix_memory_entries_hidden_from_recall",
    } <= memory_entry_indexes
    assert {
        "ix_memory_change_log_memory_id",
        "ix_memory_change_log_created_at",
    } <= memory_change_indexes


def test_subagent_migration_backfills_legacy_sessions(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "legacy_sessions.db"
    backend_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    clear_settings_cache()
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))

    command.upgrade(config, "0005_tool_catalog_policy_and_cache")

    engine = sa.create_engine(f"sqlite:///{database_path}")
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys=ON"))
        connection.execute(
            sa.text(
                """
                INSERT INTO agents (
                    id, slug, name, description, status, is_default, created_at, updated_at
                )
                VALUES (
                    :id, :slug, :name, :description, :status, :is_default, :created_at, :updated_at
                )
                """
            ),
            {
                "id": "agent-1",
                "slug": "main",
                "name": "Main Agent",
                "description": None,
                "status": "active",
                "is_default": 1,
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO sessions (
                    id, agent_id, title, summary, status,
                    started_at, last_message_at, created_at, updated_at
                )
                VALUES (
                    :id, :agent_id, :title, :summary, :status,
                    :started_at, :last_message_at, :created_at, :updated_at
                )
                """
            ),
            {
                "id": "session-1",
                "agent_id": "agent-1",
                "title": "Legacy Session",
                "summary": None,
                "status": "active",
                "started_at": now,
                "last_message_at": None,
                "created_at": now,
                "updated_at": now,
            },
        )

    clear_settings_cache()
    command.upgrade(config, "head")

    upgraded_engine = sa.create_engine(f"sqlite:///{database_path}")
    with upgraded_engine.begin() as connection:
        row = (
            connection.execute(
                sa.text(
                    """
                SELECT kind, parent_session_id, root_session_id, spawn_depth
                FROM sessions
                WHERE id = :id
                """
                ),
                {"id": "session-1"},
            )
            .mappings()
            .one()
        )

    assert row["kind"] == "main"
    assert row["parent_session_id"] is None
    assert row["root_session_id"] == "session-1"
    assert row["spawn_depth"] == 0


def test_memory_v1_migration_backfills_legacy_memories(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "legacy_memories.db"
    backend_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    clear_settings_cache()
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))

    command.upgrade(config, "0007_subagent_runtime_hardening")

    engine = sa.create_engine(f"sqlite:///{database_path}")
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys=ON"))
        connection.execute(
            sa.text(
                """
                INSERT INTO agents (
                    id, slug, name, description, status, is_default, created_at, updated_at
                )
                VALUES (
                    :id, :slug, :name, :description, :status, :is_default, :created_at, :updated_at
                )
                """
            ),
            {
                "id": "agent-1",
                "slug": "main",
                "name": "Main Agent",
                "description": None,
                "status": "active",
                "is_default": 1,
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO memories (
                    id,
                    agent_id,
                    namespace,
                    memory_key,
                    value_text,
                    source,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :agent_id,
                    :namespace,
                    :memory_key,
                    :value_text,
                    :source,
                    :status,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": "legacy-memory-1",
                "agent_id": "agent-1",
                "namespace": "default",
                "memory_key": "project-style",
                "value_text": (
                    "The product is SQLite-first and uses the database as the source of truth."
                ),
                "source": "manual",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )

    clear_settings_cache()
    command.upgrade(config, "head")

    upgraded_engine = sa.create_engine(f"sqlite:///{database_path}")
    with upgraded_engine.begin() as connection:
        row = (
            connection.execute(
                sa.text(
                    """
                SELECT scope_type, scope_key, source_kind, lifecycle_state, title, body, created_by
                FROM memory_entries
                WHERE id = :id
                """
                ),
                {"id": "legacy-memory-1"},
            )
            .mappings()
            .one()
        )

    assert row["scope_type"] == "stable"
    assert row["scope_key"] == "legacy/default/project-style"
    assert row["source_kind"] == "manual"
    assert row["lifecycle_state"] == "active"
    assert row["title"] == "project-style"
    assert "SQLite-first" in row["body"]
    assert row["created_by"] == "migration"
