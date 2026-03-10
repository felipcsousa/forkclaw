from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.tool import (
    ToolCallRead,
    ToolCallsResponse,
    ToolPermissionRead,
    ToolPermissionsResponse,
    ToolPermissionUpdate,
)
from app.services.tools import ToolService

router = APIRouter(tags=["tools"])


@router.get("/tools/permissions", response_model=ToolPermissionsResponse)
def list_tool_permissions(session: Session = Depends(get_session)) -> ToolPermissionsResponse:
    service = ToolService(session)

    try:
        workspace_root, items = service.list_permissions()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ToolPermissionsResponse(
        workspace_root=workspace_root,
        items=[ToolPermissionRead.model_validate(item) for item in items],
    )


@router.put("/tools/permissions/{tool_name}", response_model=ToolPermissionRead)
def update_tool_permission(
    tool_name: str,
    payload: ToolPermissionUpdate,
    session: Session = Depends(get_session),
) -> ToolPermissionRead:
    service = ToolService(session)

    try:
        item = service.update_permission(tool_name, payload.permission_level)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ToolPermissionRead.model_validate(item)


@router.get("/tools/calls", response_model=ToolCallsResponse)
def list_tool_calls(session: Session = Depends(get_session)) -> ToolCallsResponse:
    service = ToolService(session)

    try:
        items = service.list_tool_calls()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ToolCallsResponse(items=[ToolCallRead.model_validate(item) for item in items])
