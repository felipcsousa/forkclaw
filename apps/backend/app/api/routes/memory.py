from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.errors import value_error_as_http_exception
from app.db.session import get_session
from app.schemas.memory import (
    MemoryDeleteResponse,
    MemoryEntriesListResponse,
    MemoryEntryCreate,
    MemoryEntryHistoryResponse,
    MemoryEntryRead,
    MemoryEntryUpdate,
    MemoryHistoryItemRead,
    MemoryItemCreate,
    MemoryItemHistoryResponse,
    MemoryItemRead,
    MemoryItemsResponse,
    MemoryItemUpdate,
    MemoryRecallDetailRead,
    MemoryRecallLogResponse,
    MemoryRecallPreviewResponse,
    MemoryScopeName,
    MemoryScopesResponse,
    MemorySearchResponse,
    SessionRecallSummariesResponse,
)
from app.services.memory import MemoryService
from app.services.memory_admin_service import (
    MemoryAdminService,
    MemoryConflictError,
    MemoryFeatureDisabledError,
    MemoryHardDeleteDisabledError,
    MemoryManualCrudDisabledError,
)
from app.services.memory_search_service import MemorySearchService

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
    memory_id: str,
    session: Session = Depends(get_session),
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
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryEntryRead:
    service = MemoryAdminService(session)
    try:
        item = service.restore(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryRead.model_validate(item)


@router.get("/memory/entries/{memory_id}/history", response_model=MemoryEntryHistoryResponse)
def list_memory_history(
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryEntryHistoryResponse:
    service = MemoryAdminService(session)
    try:
        items = service.list_history(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryEntryHistoryResponse(
        items=[MemoryHistoryItemRead.model_validate(item) for item in items]
    )


@router.get("/memory/search", response_model=MemorySearchResponse)
def search_memory(
    q: str = Query(min_length=1),
    session_id: str | None = Query(default=None),
    scope: list[MemoryScopeName] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> MemorySearchResponse:
    service = MemorySearchService(session)
    try:
        return service.search(q=q, session_id=session_id, scopes=scope, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.get("/memory/recall/preview", response_model=MemoryRecallPreviewResponse)
def preview_memory_recall(
    q: str = Query(min_length=1),
    session_id: str | None = Query(default=None),
    scope: list[MemoryScopeName] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    run_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> MemoryRecallPreviewResponse:
    service = MemorySearchService(session)
    try:
        return service.recall_preview(
            q=q,
            session_id=session_id,
            scopes=scope,
            limit=limit,
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.get("/memory/scopes", response_model=MemoryScopesResponse)
def list_memory_scopes(
    session_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> MemoryScopesResponse:
    service = MemorySearchService(session)
    try:
        return service.list_scopes(session_id=session_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.get("/memory/items", response_model=MemoryItemsResponse, response_model_exclude_none=True)
def list_memory_items(
    kind: str | None = Query(default=None),
    query: str | None = Query(default=None),
    scope: str | None = Query(default=None),
    source_kind: str | None = Query(default=None),
    state: str | None = Query(default=None),
    recall_status: str | None = Query(default=None),
    mode: str = Query(default="all"),
    session: Session = Depends(get_session),
) -> MemoryItemsResponse:
    items = MemoryService(session).list_items(
        kind=kind,
        query=query,
        scope=scope,
        source_kind=source_kind,
        state=state,
        recall_status=recall_status,
        mode=mode,
    )
    return MemoryItemsResponse(items=items)


@router.post(
    "/memory/items",
    response_model=MemoryItemRead,
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_none=True,
)
def create_memory_item(
    payload: MemoryItemCreate,
    session: Session = Depends(get_session),
) -> MemoryItemRead:
    try:
        return MemoryService(session).create_item(payload)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.get(
    "/memory/items/{memory_id}", response_model=MemoryItemRead, response_model_exclude_none=True
)
def get_memory_item(
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryItemRead:
    try:
        return MemoryService(session).get_item(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.put(
    "/memory/items/{memory_id}", response_model=MemoryItemRead, response_model_exclude_none=True
)
def update_memory_item(
    memory_id: str,
    payload: MemoryItemUpdate,
    session: Session = Depends(get_session),
) -> MemoryItemRead:
    try:
        return MemoryService(session).update_item(memory_id, payload)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.post(
    "/memory/items/{memory_id}/hide",
    response_model=MemoryItemRead,
    response_model_exclude_none=True,
)
def hide_memory_item(
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryItemRead:
    try:
        return MemoryService(session).hide_item(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.post(
    "/memory/items/{memory_id}/restore",
    response_model=MemoryItemRead,
    response_model_exclude_none=True,
)
def restore_memory_item(
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryItemRead:
    try:
        return MemoryService(session).restore_item(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.post(
    "/memory/items/{memory_id}/promote",
    response_model=MemoryItemRead,
    response_model_exclude_none=True,
)
def promote_memory_item(
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryItemRead:
    try:
        return MemoryService(session).promote_item(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.post(
    "/memory/items/{memory_id}/demote",
    response_model=MemoryItemRead,
    response_model_exclude_none=True,
)
def demote_memory_item(
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryItemRead:
    try:
        return MemoryService(session).demote_item(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.delete(
    "/memory/items/{memory_id}",
    status_code=status.HTTP_200_OK,
    response_model=MemoryDeleteResponse | MemoryItemRead,
)
def delete_memory_item(
    memory_id: str,
    hard: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> MemoryDeleteResponse | MemoryItemRead:
    try:
        deleted = MemoryService(session).delete_item(memory_id, hard=hard)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    if hard:
        return MemoryDeleteResponse(deleted=True)
    return deleted


@router.get(
    "/memory/items/{memory_id}/history",
    response_model=MemoryItemHistoryResponse,
    response_model_exclude_none=True,
)
def get_memory_item_history(
    memory_id: str,
    session: Session = Depends(get_session),
) -> MemoryItemHistoryResponse:
    try:
        items = MemoryService(session).history_for_item(memory_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc
    return MemoryItemHistoryResponse(items=items)


@router.get(
    "/memory/recall/messages/{assistant_message_id}",
    response_model=MemoryRecallDetailRead,
    response_model_exclude_none=True,
)
def get_memory_recall_for_message(
    assistant_message_id: str,
    session: Session = Depends(get_session),
) -> MemoryRecallDetailRead:
    try:
        return MemoryService(session).recall_for_message(assistant_message_id)
    except Exception as exc:  # noqa: BLE001
        raise _memory_http_exception(exc) from exc


@router.get(
    "/memory/recall/sessions/{session_id}",
    response_model=SessionRecallSummariesResponse,
    response_model_exclude_none=True,
)
def list_session_memory_recalls(
    session_id: str,
    session: Session = Depends(get_session),
) -> SessionRecallSummariesResponse:
    items = MemoryService(session).recall_for_session(session_id)
    return SessionRecallSummariesResponse(items=items)


@router.get(
    "/memory/recall", response_model=MemoryRecallLogResponse, response_model_exclude_none=True
)
def list_memory_recall_log(session: Session = Depends(get_session)) -> MemoryRecallLogResponse:
    return MemoryRecallLogResponse(items=MemoryService(session).recall_log())
