from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.activity import ActivityTimelineResponse
from app.services.activity import ActivityService

router = APIRouter(tags=["activity"])


@router.get("/activity/timeline", response_model=ActivityTimelineResponse)
def get_activity_timeline(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ActivityTimelineResponse:
    service = ActivityService(session)
    try:
        return service.get_timeline(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
