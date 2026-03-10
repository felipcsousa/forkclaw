from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.secrets import SecretStoreError
from app.db.session import get_session
from app.schemas.operational_settings import (
    OperationalSettingsRead,
    OperationalSettingsUpdate,
)
from app.schemas.settings import SettingRead, SettingsListResponse
from app.services.agent_os import AgentOSService
from app.services.operational_settings import OperationalSettingsService

router = APIRouter(tags=["settings"])


def _status_from_value_error(exc: ValueError) -> int:
    return (
        status.HTTP_404_NOT_FOUND
        if "not found" in str(exc).lower()
        else status.HTTP_400_BAD_REQUEST
    )


@router.get("/settings", response_model=SettingsListResponse)
def list_settings(session: Session = Depends(get_session)) -> SettingsListResponse:
    service = AgentOSService(session)
    items = [SettingRead.model_validate(item) for item in service.list_settings()]
    return SettingsListResponse(items=items)


@router.get("/settings/operational", response_model=OperationalSettingsRead)
def get_operational_settings(
    session: Session = Depends(get_session),
) -> OperationalSettingsRead:
    service = OperationalSettingsService(session)
    try:
        return service.get_operational_settings()
    except ValueError as exc:
        raise HTTPException(status_code=_status_from_value_error(exc), detail=str(exc)) from exc
    except SecretStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.put("/settings/operational", response_model=OperationalSettingsRead)
def update_operational_settings(
    payload: OperationalSettingsUpdate,
    session: Session = Depends(get_session),
) -> OperationalSettingsRead:
    service = OperationalSettingsService(session)
    try:
        return service.update_operational_settings(payload)
    except ValueError as exc:
        raise HTTPException(status_code=_status_from_value_error(exc), detail=str(exc)) from exc
    except SecretStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
