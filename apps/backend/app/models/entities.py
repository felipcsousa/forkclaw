from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def generate_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class TimestampedModel(SQLModel):
    created_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": utc_now},
    )


class Agent(TimestampedModel, table=True):
    __tablename__ = "agents"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    slug: str = Field(sa_column=Column(String(100), nullable=False, unique=True, index=True))
    name: str = Field(sa_column=Column(String(200), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False, index=True))
    is_default: bool = Field(default=False, nullable=False)


class AgentProfile(TimestampedModel, table=True):
    __tablename__ = "agent_profiles"

    __table_args__ = (UniqueConstraint("agent_id"),)

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str = Field(foreign_key="agents.id", max_length=36, nullable=False)
    display_name: str = Field(sa_column=Column(String(200), nullable=False))
    persona: str = Field(sa_column=Column(String(200), nullable=False))
    system_prompt: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    identity_text: str = Field(default="", sa_column=Column(Text, nullable=False))
    soul_text: str = Field(default="", sa_column=Column(Text, nullable=False))
    user_context_text: str = Field(default="", sa_column=Column(Text, nullable=False))
    policy_base_text: str = Field(default="", sa_column=Column(Text, nullable=False))
    model_provider: str | None = Field(default=None, sa_column=Column(String(100), nullable=True))
    model_name: str | None = Field(default=None, sa_column=Column(String(100), nullable=True))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False))


class SessionRecord(TimestampedModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str = Field(foreign_key="agents.id", max_length=36, nullable=False, index=True)
    title: str = Field(sa_column=Column(String(200), nullable=False))
    summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False, index=True))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True)))
    last_message_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )


class Message(TimestampedModel, table=True):
    __tablename__ = "messages"

    __table_args__ = (UniqueConstraint("session_id", "sequence_number"),)

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    session_id: str = Field(foreign_key="sessions.id", max_length=36, nullable=False)
    role: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    status: str = Field(default="committed", sa_column=Column(String(50), nullable=False))
    sequence_number: int = Field(nullable=False)
    content_text: str = Field(sa_column=Column(Text, nullable=False))


class Task(TimestampedModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str = Field(foreign_key="agents.id", max_length=36, nullable=False, index=True)
    cron_job_id: str | None = Field(default=None, foreign_key="cron_jobs.id", max_length=36)
    session_id: str | None = Field(default=None, foreign_key="sessions.id", max_length=36)
    title: str = Field(sa_column=Column(String(200), nullable=False))
    kind: str = Field(default="background", sa_column=Column(String(100), nullable=False))
    status: str = Field(default="pending", sa_column=Column(String(50), nullable=False, index=True))
    payload_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    scheduled_for: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class TaskRun(TimestampedModel, table=True):
    __tablename__ = "task_runs"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    task_id: str = Field(foreign_key="tasks.id", max_length=36, nullable=False)
    status: str = Field(default="pending", sa_column=Column(String(50), nullable=False, index=True))
    attempt: int = Field(default=1, nullable=False)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    duration_ms: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    estimated_cost_usd: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    output_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class ToolPermission(TimestampedModel, table=True):
    __tablename__ = "tool_permissions"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str = Field(foreign_key="agents.id", max_length=36, nullable=False, index=True)
    tool_name: str = Field(sa_column=Column(String(100), nullable=False))
    workspace_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    permission_level: str = Field(default="ask", sa_column=Column(String(50), nullable=False))
    approval_required: bool = Field(default=True, nullable=False)
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False))


class ToolPolicyOverride(TimestampedModel, table=True):
    __tablename__ = "tool_policy_overrides"

    __table_args__ = (UniqueConstraint("agent_id", "tool_name"),)

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str = Field(foreign_key="agents.id", max_length=36, nullable=False, index=True)
    tool_name: str = Field(sa_column=Column(String(100), nullable=False))
    permission_level: str = Field(default="ask", sa_column=Column(String(50), nullable=False))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False))


class ToolCall(TimestampedModel, table=True):
    __tablename__ = "tool_calls"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    session_id: str | None = Field(default=None, foreign_key="sessions.id", max_length=36)
    message_id: str | None = Field(default=None, foreign_key="messages.id", max_length=36)
    task_run_id: str | None = Field(default=None, foreign_key="task_runs.id", max_length=36)
    tool_name: str = Field(sa_column=Column(String(100), nullable=False, index=True))
    status: str = Field(
        default="requested",
        sa_column=Column(String(50), nullable=False, index=True),
    )
    input_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    output_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class ToolCacheEntry(TimestampedModel, table=True):
    __tablename__ = "tool_cache_entries"

    __table_args__ = (UniqueConstraint("tool_name", "cache_key"),)

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    tool_name: str = Field(sa_column=Column(String(100), nullable=False, index=True))
    cache_key: str = Field(sa_column=Column(String(255), nullable=False))
    value_json: str = Field(sa_column=Column(Text, nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False))


class CronJob(TimestampedModel, table=True):
    __tablename__ = "cron_jobs"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str = Field(foreign_key="agents.id", max_length=36, nullable=False)
    name: str = Field(sa_column=Column(String(150), nullable=False))
    schedule: str = Field(sa_column=Column(String(255), nullable=False))
    timezone: str = Field(default="UTC", sa_column=Column(String(100), nullable=False))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False, index=True))
    task_payload_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    last_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    next_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class Memory(TimestampedModel, table=True):
    __tablename__ = "memories"

    __table_args__ = (UniqueConstraint("agent_id", "namespace", "memory_key"),)

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str = Field(foreign_key="agents.id", max_length=36, nullable=False)
    namespace: str = Field(default="default", sa_column=Column(String(100), nullable=False))
    memory_key: str = Field(sa_column=Column(String(150), nullable=False))
    value_text: str = Field(sa_column=Column(Text, nullable=False))
    source: str = Field(default="manual", sa_column=Column(String(100), nullable=False))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False))


class Document(TimestampedModel, table=True):
    __tablename__ = "documents"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str | None = Field(default=None, foreign_key="agents.id", max_length=36)
    session_id: str | None = Field(default=None, foreign_key="sessions.id", max_length=36)
    title: str = Field(sa_column=Column(String(255), nullable=False))
    content_text: str = Field(sa_column=Column(Text, nullable=False))
    content_type: str = Field(default="text/plain", sa_column=Column(String(100), nullable=False))
    source_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    checksum: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False, index=True))


class Approval(TimestampedModel, table=True):
    __tablename__ = "approvals"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str = Field(foreign_key="agents.id", max_length=36, nullable=False)
    task_id: str | None = Field(default=None, foreign_key="tasks.id", max_length=36)
    tool_call_id: str | None = Field(default=None, foreign_key="tool_calls.id", max_length=36)
    kind: str = Field(default="tool_execution", sa_column=Column(String(100), nullable=False))
    requested_action: str = Field(sa_column=Column(Text, nullable=False))
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(default="pending", sa_column=Column(String(50), nullable=False, index=True))
    decided_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    agent_id: str | None = Field(default=None, foreign_key="agents.id", max_length=36)
    actor_type: str = Field(sa_column=Column(String(50), nullable=False))
    level: str = Field(default="info", sa_column=Column(String(20), nullable=False, index=True))
    event_type: str = Field(sa_column=Column(String(100), nullable=False, index=True))
    entity_type: str = Field(sa_column=Column(String(100), nullable=False))
    entity_id: str | None = Field(default=None, sa_column=Column(String(36), nullable=True))
    summary_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    payload_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Setting(TimestampedModel, table=True):
    __tablename__ = "settings"

    __table_args__ = (UniqueConstraint("scope", "key"),)

    id: str = Field(default_factory=generate_id, primary_key=True, max_length=36)
    scope: str = Field(default="app", sa_column=Column(String(100), nullable=False, index=True))
    key: str = Field(sa_column=Column(String(150), nullable=False))
    value_type: str = Field(default="string", sa_column=Column(String(50), nullable=False))
    value_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    value_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False))
