from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.errors import value_error_as_http_exception
from app.db.session import get_session
from app.schemas.tool import (
    ToolCallRead,
    ToolCallsResponse,
    ToolCatalogEntryRead,
    ToolCatalogResponse,
    ToolPermissionRead,
    ToolPermissionsResponse,
    ToolPermissionUpdate,
    ToolPolicyOverrideRead,
    ToolPolicyProfileRead,
    ToolPolicyRead,
    ToolPolicyUpdate,
)
from app.services.tools import ToolService

router = APIRouter(tags=["tools"])


@router.get("/tools/catalog", response_model=ToolCatalogResponse)
def get_tool_catalog(session: Session = Depends(get_session)) -> ToolCatalogResponse:
    service = ToolService(session)
    items = [
        ToolCatalogEntryRead(
            id=item.id,
            label=item.label,
            description=item.description,
            group=item.group,
            group_label=item.group_label,
            risk=item.risk,
            status=item.status,
            input_schema=item.input_schema,
            output_schema=item.output_schema,
            requires_workspace=item.requires_workspace,
        )
        for item in service.list_catalog()
    ]
    return ToolCatalogResponse(items=items)


@router.get("/tools/policy", response_model=ToolPolicyRead)
def get_tool_policy(session: Session = Depends(get_session)) -> ToolPolicyRead:
    service = ToolService(session)
    try:
        profile_id, profiles, overrides = service.get_policy()
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc

    return ToolPolicyRead(
        profile_id=profile_id,
        profiles=[
            ToolPolicyProfileRead(
                id=profile.id,
                label=profile.label,
                description=profile.description,
                defaults=profile.defaults,
            )
            for profile in profiles
        ],
        overrides=[ToolPolicyOverrideRead.model_validate(item) for item in overrides],
    )


@router.put("/tools/policy", response_model=ToolPolicyRead)
def update_tool_policy(
    payload: ToolPolicyUpdate,
    session: Session = Depends(get_session),
) -> ToolPolicyRead:
    service = ToolService(session)
    try:
        profile_id, profiles, overrides = service.update_policy_profile(payload.profile_id)
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc

    return ToolPolicyRead(
        profile_id=profile_id,
        profiles=[
            ToolPolicyProfileRead(
                id=profile.id,
                label=profile.label,
                description=profile.description,
                defaults=profile.defaults,
            )
            for profile in profiles
        ],
        overrides=[ToolPolicyOverrideRead.model_validate(item) for item in overrides],
    )


@router.get("/tools/permissions", response_model=ToolPermissionsResponse)
def list_tool_permissions(session: Session = Depends(get_session)) -> ToolPermissionsResponse:
    service = ToolService(session)

    try:
        workspace_root, items = service.list_permissions()
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc

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
        raise value_error_as_http_exception(exc, default_status=404) from exc

    return ToolPermissionRead.model_validate(item)


@router.get("/tools/calls", response_model=ToolCallsResponse)
def list_tool_calls(session: Session = Depends(get_session)) -> ToolCallsResponse:
    service = ToolService(session)

    try:
        items = service.list_tool_calls()
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc

    return ToolCallsResponse(items=[ToolCallRead.model_validate(item) for item in items])
