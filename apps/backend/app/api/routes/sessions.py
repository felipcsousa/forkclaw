from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.execution import AgentExecutionResponse
from app.schemas.message import MessageRead, SessionMessageCreate, SessionMessagesResponse
from app.schemas.session import SessionCreate, SessionRead, SessionsListResponse
from app.services.agent_execution import AgentExecutionService
from app.services.agent_os import AgentOSService

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=SessionsListResponse)
def list_sessions(session: Session = Depends(get_session)) -> SessionsListResponse:
    service = AgentOSService(session)
    items = [SessionRead.model_validate(item) for item in service.list_sessions()]
    return SessionsListResponse(items=items)


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    session: Session = Depends(get_session),
) -> SessionRead:
    service = AgentOSService(session)

    try:
        record = service.create_session(payload.title)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return SessionRead.model_validate(record)


@router.get("/sessions/{session_id}", response_model=SessionRead)
def get_session_by_id(
    session_id: str,
    session: Session = Depends(get_session),
) -> SessionRead:
    service = AgentOSService(session)
    record = service.get_session(session_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    return SessionRead.model_validate(record)


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def list_session_messages(
    session_id: str,
    session: Session = Depends(get_session),
) -> SessionMessagesResponse:
    service = AgentOSService(session)
    record, messages = service.list_session_messages(session_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    return SessionMessagesResponse(
        session=SessionRead.model_validate(record),
        items=[MessageRead.model_validate(item) for item in messages],
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=AgentExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_session_message(
    session_id: str,
    payload: SessionMessageCreate,
    session: Session = Depends(get_session),
) -> AgentExecutionResponse:
    service = AgentExecutionService(session)

    try:
        return service.execute_simple(
            session_id=session_id,
            title=None,
            message=payload.content,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
