from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.errors import value_error_as_http_exception
from app.db.session import get_session
from app.schemas.memory import (
    MemoryDeleteResponse,
    MemoryEntriesListResponse,
    MemoryEntryCreate,
    MemoryEntryRead,
    MemoryEntryUpdate,
    MemoryHistoryItemRead,
    MemoryHistoryResponse,
)
from app.services.memory_admin_service import (
    MemoryAdminService,
    MemoryConflictError,
    MemoryFeatureDisabledError,
    MemoryHardDeleteDisabledError,
    MemoryManualCrudDisabledError,
)

router = APIRouter(tags=["memory"])


def _memory_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, MemoryFeatureDisabledError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, MemoryManualCrudDisabledError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, MemoryHardDeleteDisabledError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, MemoryConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "A similar memory already exists.",
                "existing_memory_id": exc.existing_memory_id,
                "reason": exc.reason,
            },
        )
    if isinstance(exc, ValueError):
        return value_error_as_http_exception(exc)
    return HTTPException(status_code=500, detail="Internal server error.")


@router.get("/memory/entries", response_model=MemoryEntriesListResponse)
def list_memory_entries(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    scope_type: str | None = None,
    source_kind: str | None = None,
    lifecycle_state: str | None = None,
    hidden: bool | None = None,
    deleted: bool | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
    search: str | None = None,
    session: Session = Depends(get_session),
) -> MemoryEntriesListResponse:
    service = MemoryAdminService(session)
    try:
        items = service.list_entries(
            limit=limit,
            offset=offset,
            scope_type=scope_type,
            source_kind=source_kind,
            lifecycle_state=lifecycle_state,
            hidden=hidden,
            deleted=deleted,
            session_id=session_id,
            conversation_id=conversation_id,
            search=search,
        )
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntriesListResponse(items=[MemoryEntryRead.model_validate(item) for item in items])


@router.get("/memory/entries/{memory_id}", response_model=MemoryEntryRead)
def get_memory_entry(
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        item = service.get_entry(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.post(
    "/memory/entries",
    response_model=MemoryEntryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_memory_entry(
    payload: MemoryEntryCreate,
    session: Session = Depends(get_session),
) -> MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        item = service.create_manual_entry(payload)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.patch("/memory/entries/{memory_id}", response_model=MemoryEntryRead)
def update_memory_entry(
    memory_id: str,
    payload: MemoryEntryUpdate,
    session: Session = Depends(get_session),
) -> MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        item = service.update_entry(memory_id, payload)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.delete("/memory/entries/{memory_id}", response_model=MemoryDeleteResponse | MemoryEntryRead)
def delete_memory_entry(
    memory_id: str,
    hard: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> MemoryDeleteResponse | MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        if hard:
            return MemoryDeleteResponse.model_validate(service.hard_delete(memory_id))
        item = service.soft_delete(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.post("/memory/entries/{memory_id}/hide", response_model=MemoryEntryRead)
def hide_memory_entry(memory_id: str, session: Session = Depends(get_session)) -> MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        item = service.hide(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.post("/memory/entries/{memory_id}/unhide", response_model=MemoryEntryRead)
def unhide_memory_entry(memory_id: str, session: Session = Depends(get_session)) -> MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        item = service.unhide(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.post("/memory/entries/{memory_id}/promote", response_model=MemoryEntryRead)
def promote_memory_entry(
    memory_id: str, session: Session = Depends(get_session)
) -> MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        item = service.promote(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.post("/memory/entries/{memory_id}/demote", response_model=MemoryEntryRead)
def demote_memory_entry(memory_id: str, session: Session = Depends(get_session)) -> MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        item = service.demote(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.post("/memory/entries/{memory_id}/restore", response_model=MemoryEntryRead)
def restore_memory_entry(
    memory_id: str, session: Session = Depends(get_session)
) -> MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        item = service.restore(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.get("/memory/entries/{memory_id}/history", response_model=MemoryHistoryResponse)
def list_memory_history(
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryHistoryResponse:
    service = MemoryAdminService(session)
    try:
        items = service.list_history(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryHistoryResponse(
        items=[MemoryHistoryItemRead.model_validate(item) for item in items]
    )
