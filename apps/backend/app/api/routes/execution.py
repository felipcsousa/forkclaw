from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.execution import AgentExecutionCreate, AgentExecutionResponse
from app.services.agent_execution import AgentExecutionService

router = APIRouter(tags=["agent-execution"])


@router.post(
    "/agent/execute",
    response_model=AgentExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
def execute_agent(
    payload: AgentExecutionCreate,
    session: Session = Depends(get_session),
) -> AgentExecutionResponse:
    service = AgentExecutionService(session)

    try:
        return service.execute_simple(
            session_id=payload.session_id,
            title=payload.title,
            message=payload.message,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
