from __future__ import annotations

from sqlalchemy import inspect

from app.db.session import get_engine


def test_schema_and_migrations_create_required_tables(test_client) -> None:
    del test_client
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())

    assert tables >= {
        "agents",
        "agent_profiles",
        "sessions",
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

    assert {"duration_ms", "estimated_cost_usd"} <= task_runs_columns
    assert {"level", "summary_text"} <= audit_events_columns
    assert {"tool_name", "cache_key", "value_json", "expires_at"} <= tool_cache_columns
