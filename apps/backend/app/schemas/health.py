from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


OperationalComponentStatus = Literal["starting", "running", "degraded", "stopped"]
OperationalHealthStatus = Literal["ok", "degraded"]


class OperationalComponentHealthResponse(BaseModel):
    status: OperationalComponentStatus
    poll_interval_seconds: float
    last_tick_started_at: datetime | None = None
    last_tick_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    consecutive_failures: int = 0
    last_error_summary: str | None = None


class OperationalBacklogHealthResponse(BaseModel):
    queued_subagents: int = 0
    running_subagents: int = 0
    active_cron_jobs: int = 0
    due_cron_jobs: int = 0
    pending_approvals: int = 0


class OperationalComponentsHealthResponse(BaseModel):
    scheduler: OperationalComponentHealthResponse
    execution_worker: OperationalComponentHealthResponse
    subagent_worker: OperationalComponentHealthResponse


class OperationalHealthResponse(BaseModel):
    status: OperationalHealthStatus
    service: str
    version: str
    components: OperationalComponentsHealthResponse
    backlog: OperationalBacklogHealthResponse
