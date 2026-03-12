from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic import Field as PydanticField

SessionKind = Literal["main", "subagent"]
SubagentLifecycleStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "timed_out",
]


class SessionCreate(BaseModel):
    title: str | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    kind: SessionKind
    parent_session_id: str | None
    root_session_id: str | None
    spawn_depth: int
    title: str
    summary: str | None
    status: str
    delegated_goal: str | None
    delegated_context_snapshot: str | None
    tool_profile: str | None
    model_override: str | None
    max_iterations: int | None
    timeout_seconds: float | None
    started_at: datetime
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime
    subagent_counts: SubagentCountsRead | None = None


class SessionsListResponse(BaseModel):
    items: list[SessionRead]


class SubagentCountsRead(BaseModel):
    total: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    timed_out: int = 0


class SubagentSpawnRequest(BaseModel):
    goal: str = PydanticField(min_length=1)
    context: str | None = None
    toolsets: list[str] = PydanticField(default_factory=list)
    model: str | None = None
    max_iterations: int | None = PydanticField(default=None, ge=1)
    timeout_seconds: float | None = PydanticField(default=None, gt=0)
    launcher_message_id: str | None = None
    launcher_task_run_id: str | None = None

    @field_validator("goal")
    @classmethod
    def _trim_and_validate_goal(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            msg = "String should have at least 1 character"
            raise ValueError(msg)
        return trimmed


class SubagentSpawnResponse(BaseModel):
    parent_session_id: str
    child_session_id: str
    status: Literal["accepted"]
    spawn_depth: int
    toolsets: list[str]
    model: str | None
    max_iterations: int | None
    timeout_seconds: float


class SubagentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    launcher_session_id: str
    child_session_id: str
    launcher_message_id: str | None
    launcher_task_run_id: str | None
    task_id: str | None
    task_run_id: str | None
    parent_summary_message_id: str | None
    lifecycle_status: SubagentLifecycleStatus
    started_at: datetime | None
    finished_at: datetime | None
    cancellation_requested_at: datetime | None
    final_summary: str | None
    final_output_json: str | None
    estimated_cost_usd: float | None
    error_code: str | None
    error_summary: str | None
    created_at: datetime
    updated_at: datetime


class SubagentTimelineEventRead(BaseModel):
    id: str
    event_type: str
    created_at: datetime
    status: SubagentLifecycleStatus | None = None
    summary: str
    task_run_id: str | None = None
    estimated_cost_usd: float | None = None


class SubagentSessionRead(SessionRead):
    run: SubagentRunRead
    timeline_events: list[SubagentTimelineEventRead] = PydanticField(default_factory=list)


class SessionSubagentsListResponse(BaseModel):
    parent_session_id: str
    items: list[SubagentSessionRead]


class SubagentCancelResponse(BaseModel):
    parent_session_id: str
    child_session_id: str
    lifecycle_status: SubagentLifecycleStatus
    cancellation_requested_at: datetime | None
    finished_at: datetime | None


SessionRead.model_rebuild()
SubagentSessionRead.model_rebuild()
