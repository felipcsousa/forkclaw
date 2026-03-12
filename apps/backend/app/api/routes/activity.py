from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.errors import value_error_as_http_exception
from app.db.session import get_session
from app.schemas.activity import ActivityTimelineResponse
from app.services.activity import ActivityService

router = APIRouter(tags=["activity"])


@router.get(
    "/activity/timeline",
    response_model=ActivityTimelineResponse,
    response_model_exclude_none=True,
)
def get_activity_timeline(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> ActivityTimelineResponse:
    service = ActivityService(session)
    try:
        return service.get_timeline(limit=limit, cursor=cursor)
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc
