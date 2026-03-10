from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobType = Literal[
    "review_pending_approvals",
    "summarize_recent_activity",
    "cleanup_stale_runs",
]


class CronJobPayload(BaseModel):
    job_type: JobType
    message: str | None = Field(default=None, max_length=500)
    stale_after_seconds: int | None = Field(default=None, ge=30, le=86400)


class CronJobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    schedule: str = Field(min_length=1, max_length=255)
    timezone: str | None = Field(default=None, max_length=100)
    payload: CronJobPayload


class CronJobUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    schedule: str | None = Field(default=None, min_length=1, max_length=255)
    timezone: str | None = Field(default=None, max_length=100)
    payload: CronJobPayload | None = None


class CronJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    name: str
    schedule: str
    timezone: str
    status: str
    task_payload_json: str | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    payload: CronJobPayload


class TaskRunHistoryRead(BaseModel):
    task_run_id: str
    task_id: str
    cron_job_id: str | None
    task_title: str
    task_kind: str
    task_status: str
    job_name: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    output_summary: str | None
    created_at: datetime


class HeartbeatStatusRead(BaseModel):
    last_run_at: datetime | None
    task_run_id: str | None
    cleaned_stale_runs: int
    pending_approvals: int
    recent_task_runs: int
    summary_text: str


class CronJobsDashboardResponse(BaseModel):
    items: list[CronJobRead]
    history: list[TaskRunHistoryRead]
    heartbeat: HeartbeatStatusRead
