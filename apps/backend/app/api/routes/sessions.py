from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.errors import value_error_as_http_exception
from app.db.session import get_db_session, get_session
from app.schemas.execution import AgentExecutionAcceptedResponse, AgentExecutionResponse
from app.schemas.message import MessageRead, SessionMessageCreate, SessionMessagesResponse
from app.schemas.session import (
    SessionCreate,
    SessionRead,
    SessionsListResponse,
    SessionSubagentsListResponse,
    SubagentCancelResponse,
    SubagentSessionRead,
    SubagentSpawnRequest,
    SubagentSpawnResponse,
)
from app.services.agent_execution import AgentExecutionService
from app.services.agent_os import AgentOSService
from app.services.execution_events import ExecutionEventService
from app.services.subagents import SubagentDelegationService

router = APIRouter(tags=["sessions"])


def ensure_main_session(
    session_id: str,
    session: Session = Depends(get_session),
) -> None:
    subagents = SubagentDelegationService(session)
    try:
        subagents.ensure_main_session_interaction_allowed(session_id)
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.get("/sessions", response_model=SessionsListResponse, response_model_exclude_none=True)
def list_sessions(
    include_subagent_counts: bool = False,
    session: Session = Depends(get_session),
) -> SessionsListResponse:
    service = AgentOSService(session)
    subagents = SubagentDelegationService(session)
    records = service.list_sessions()
    counts = (
        subagents.aggregate_counts_for_sessions([item.id for item in records])
        if include_subagent_counts
        else {}
    )
    items = [
        SessionRead.model_validate({**item.model_dump(), "subagent_counts": counts.get(item.id)})
        for item in records
    ]
    return SessionsListResponse(items=items)


@router.post(
    "/sessions",
    response_model=SessionRead,
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_none=True,
)
def create_session(
    payload: SessionCreate,
    session: Session = Depends(get_session),
) -> SessionRead:
    service = AgentOSService(session)

    try:
        record = service.create_session(payload.title)
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc

    return SessionRead.model_validate(record)


@router.get("/sessions/{session_id}", response_model=SessionRead, response_model_exclude_none=True)
def get_session_by_id(
    session_id: str,
    session: Session = Depends(get_session),
) -> SessionRead:
    record = SubagentDelegationService(session).get_main_session(session_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    return SessionRead.model_validate(record)


@router.post(
    "/sessions/{session_id}/reset",
    response_model=SessionRead,
)
def reset_session_conversation(
    session_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(ensure_main_session),
) -> SessionRead:

    service = AgentOSService(session)
    try:
        record = service.reset_session_conversation(session_id)
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc

    return SessionRead.model_validate(record)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=SessionMessagesResponse,
    response_model_exclude_none=True,
)
def list_session_messages(
    session_id: str,
    limit: int | None = Query(default=None, ge=1, le=200),
    before_sequence: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_session),
    _: None = Depends(ensure_main_session),
) -> SessionMessagesResponse:

    service = AgentOSService(session)
    record, messages, has_more, next_before_sequence = service.list_session_messages(
        session_id,
        limit=limit,
        before_sequence=before_sequence,
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    return SessionMessagesResponse(
        session=SessionRead.model_validate(record),
        items=[MessageRead.model_validate(item) for item in messages],
        has_more=has_more,
        next_before_sequence=next_before_sequence,
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
    _: None = Depends(ensure_main_session),
) -> AgentExecutionResponse:

    service = AgentExecutionService(session)

    try:
        return service.execute_simple(
            session_id=session_id,
            title=None,
            message=payload.content,
        )
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.post(
    "/sessions/{session_id}/messages/async",
    response_model=AgentExecutionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_session_message_async(
    session_id: str,
    payload: SessionMessageCreate,
    session: Session = Depends(get_session),
    _: None = Depends(ensure_main_session),
) -> AgentExecutionAcceptedResponse:

    service = AgentExecutionService(session)

    try:
        return service.enqueue_simple(
            session_id=session_id,
            title=None,
            message=payload.content,
        )
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.get("/sessions/{session_id}/events")
async def stream_session_events(
    session_id: str,
    request: Request,
    task_run_id: str | None = Query(default=None),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    with get_db_session() as session:
        subagents = SubagentDelegationService(session)
        try:
            subagents.ensure_main_session_interaction_allowed(session_id)
        except ValueError as exc:
            raise value_error_as_http_exception(exc) from exc

        if AgentOSService(session).get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

    async def _event_stream():
        cursor = last_event_id
        replay_complete_sent = task_run_id is not None
        terminal_types = {"execution.completed", "execution.failed", "approval.requested"}
        while True:
            with get_db_session() as session:
                service = ExecutionEventService(session)
                events = service.list_events(
                    session_id=session_id,
                    task_run_id=task_run_id,
                    after_event_id=cursor,
                )
            for event in events:
                cursor = event.id
                yield (
                    f"id: {event.id}\n"
                    f"event: {event.type}\n"
                    f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                )
                if task_run_id is not None and event.type in terminal_types:
                    return
            if not replay_complete_sent:
                replay_complete_sent = True
                ready_payload = {
                    "type": "stream.ready",
                    "session_id": session_id,
                    "data": {"phase": "live"},
                }
                yield (
                    "event: stream.ready\n"
                    f"data: {json.dumps(ready_payload, ensure_ascii=False)}\n\n"
                )
            if await request.is_disconnected():
                break
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/sessions/{session_id}/subagents",
    response_model=SubagentSpawnResponse,
    status_code=status.HTTP_201_CREATED,
)
def spawn_subagent(
    session_id: str,
    payload: SubagentSpawnRequest,
    session: Session = Depends(get_session),
) -> SubagentSpawnResponse:
    service = SubagentDelegationService(session)
    try:
        return service.spawn(parent_session_id=session_id, payload=payload)
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.get(
    "/sessions/{session_id}/subagents",
    response_model=SessionSubagentsListResponse,
    response_model_exclude_none=True,
)
def list_subagents(
    session_id: str,
    session: Session = Depends(get_session),
) -> SessionSubagentsListResponse:
    service = SubagentDelegationService(session)
    try:
        return service.list(session_id)
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.get(
    "/sessions/{session_id}/subagents/{child_session_id}",
    response_model=SubagentSessionRead,
    response_model_exclude_none=True,
)
def get_subagent(
    session_id: str,
    child_session_id: str,
    session: Session = Depends(get_session),
) -> SubagentSessionRead:
    service = SubagentDelegationService(session)
    try:
        return service.get(
            parent_session_id=session_id,
            child_session_id=child_session_id,
        )
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.get(
    "/sessions/{session_id}/subagents/{child_session_id}/messages",
    response_model=SessionMessagesResponse,
    response_model_exclude_none=True,
)
def list_subagent_messages(
    session_id: str,
    child_session_id: str,
    limit: int | None = Query(default=None, ge=1, le=200),
    before_sequence: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_session),
) -> SessionMessagesResponse:
    service = SubagentDelegationService(session)
    try:
        child, messages, has_more, next_before_sequence = service.list_messages(
            parent_session_id=session_id,
            child_session_id=child_session_id,
            limit=limit,
            before_sequence=before_sequence,
        )
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc

    return SessionMessagesResponse(
        session=SessionRead.model_validate(child),
        items=[MessageRead.model_validate(item) for item in messages],
        has_more=has_more,
        next_before_sequence=next_before_sequence,
    )


@router.post(
    "/sessions/{session_id}/subagents/{child_session_id}/cancel",
    response_model=SubagentCancelResponse,
)
def cancel_subagent(
    session_id: str,
    child_session_id: str,
    session: Session = Depends(get_session),
) -> SubagentCancelResponse:
    service = SubagentDelegationService(session)
    try:
        return service.cancel(
            parent_session_id=session_id,
            child_session_id=child_session_id,
        )
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc
