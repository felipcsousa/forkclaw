from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.skill import SkillSummaryRead

TimelineEntryType = Literal["message", "task", "tool_call", "approval", "status", "audit"]


class ActivityAuditEventRead(BaseModel):
    id: str
    level: str
    event_type: str
    entity_type: str
    entity_id: str | None
    summary_text: str | None
    payload_json: str | None
    created_at: datetime


class ActivityTimelineEntryRead(BaseModel):
    id: str
    type: TimelineEntryType
    created_at: datetime
    status: str | None
    title: str
    summary: str
    error_message: str | None = None
    duration_ms: int | None = None
    estimated_cost_usd: float | None = None
    metadata: dict[str, Any] | None = None


class ActivityTimelineItemRead(BaseModel):
    task_run_id: str
    task_id: str
    task_kind: str
    task_title: str
    session_id: str | None
    session_title: str | None
    started_at: datetime | None
    finished_at: datetime | None
    status: str
    error_message: str | None
    duration_ms: int | None
    estimated_cost_usd: float | None
    skill_strategy: str | None = None
    resolved_skills: list[SkillSummaryRead] = Field(default_factory=list)
    entries: list[ActivityTimelineEntryRead]
    audit_log: list[ActivityAuditEventRead]


class ActivityTimelineResponse(BaseModel):
    items: list[ActivityTimelineItemRead]
