from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.health import HealthResponse, OperationalHealthResponse
from app.services.runtime_supervisor import RuntimeSupervisor

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(session: Session = Depends(get_session)) -> HealthResponse:
    session.exec(text("SELECT 1"))
    return HealthResponse(status="ok", service="backend", version="0.1.0")


@router.get(
    "/health/operational",
    response_model=OperationalHealthResponse,
    response_model_exclude_none=True,
)
async def operational_health_check(
    request: Request,
    session: Session = Depends(get_session),
) -> OperationalHealthResponse:
    session.exec(text("SELECT 1"))
    runtime_supervisor = getattr(request.app.state, "runtime_supervisor", None)
    if isinstance(runtime_supervisor, RuntimeSupervisor):
        return runtime_supervisor.operational_health(session)

    return OperationalHealthResponse(
        status="degraded",
        service="backend",
        version="0.1.0",
        components={
            "scheduler": {
                "status": "stopped",
                "poll_interval_seconds": 0,
                "consecutive_failures": 0,
            },
            "subagent_worker": {
                "status": "stopped",
                "poll_interval_seconds": 0,
                "consecutive_failures": 0,
            },
        },
        backlog={
            "queued_subagents": 0,
            "running_subagents": 0,
            "active_cron_jobs": 0,
            "due_cron_jobs": 0,
            "pending_approvals": 0,
        },
    )
