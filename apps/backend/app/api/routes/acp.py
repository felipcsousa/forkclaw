from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.errors import value_error_as_http_exception
from app.db.session import get_session
from app.schemas.acp import (
    AcpBridgeStatusRead,
    AcpBridgeStatusUpdate,
    AcpCancelRequest,
    AcpCancelResponse,
    AcpLoadSessionRequest,
    AcpLoadSessionResponse,
    AcpNewSessionRequest,
    AcpNewSessionResponse,
    AcpPromptRequest,
    AcpPromptResponse,
    AcpSessionsListResponse,
)
from app.services.acp import AcpService

router = APIRouter(tags=["acp"])


@router.get("/acp/status", response_model=AcpBridgeStatusRead)
def get_acp_status(session: Session = Depends(get_session)) -> AcpBridgeStatusRead:
    service = AcpService(session)
    return AcpBridgeStatusRead(enabled=service.is_enabled())


@router.put("/acp/status", response_model=AcpBridgeStatusRead)
def update_acp_status(
    payload: AcpBridgeStatusUpdate,
    session: Session = Depends(get_session),
) -> AcpBridgeStatusRead:
    service = AcpService(session)
    return AcpBridgeStatusRead(enabled=service.set_enabled(payload.enabled))


@router.get("/acp/sessions", response_model=AcpSessionsListResponse)
def list_acp_sessions(session: Session = Depends(get_session)) -> AcpSessionsListResponse:
    service = AcpService(session)
    return AcpSessionsListResponse(items=service.list_sessions())


@router.post("/acp/sessions", response_model=AcpNewSessionResponse)
def create_acp_session(
    payload: AcpNewSessionRequest,
    session: Session = Depends(get_session),
) -> AcpNewSessionResponse:
    service = AcpService(session)
    try:
        return service.create_session(
            label=payload.label,
            runtime=payload.runtime,
            parent_session_id=payload.parent_session_id,
        )
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.post("/acp/prompt", response_model=AcpPromptResponse)
def acp_prompt(
    payload: AcpPromptRequest,
    session: Session = Depends(get_session),
) -> AcpPromptResponse:
    service = AcpService(session)
    try:
        return service.prompt(session_key=payload.session_key, text=payload.text)
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.post("/acp/cancel", response_model=AcpCancelResponse)
def acp_cancel(
    payload: AcpCancelRequest,
    session: Session = Depends(get_session),
) -> AcpCancelResponse:
    service = AcpService(session)
    try:
        return service.cancel(session_key=payload.session_key)
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.post("/acp/load_session", response_model=AcpLoadSessionResponse)
def acp_load_session(
    payload: AcpLoadSessionRequest,
    session: Session = Depends(get_session),
) -> AcpLoadSessionResponse:
    service = AcpService(session)
    try:
        return service.load_session(session_key=payload.session_key, limit=payload.limit)
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc
