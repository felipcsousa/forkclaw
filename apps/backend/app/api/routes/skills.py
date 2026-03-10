from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.errors import value_error_as_http_exception
from app.db.session import get_session
from app.schemas.skill import SkillRead, SkillsListResponse, SkillUpdate
from app.services.skills import SkillService

router = APIRouter(tags=["skills"])


@router.get("/skills", response_model=SkillsListResponse)
def list_skills(session: Session = Depends(get_session)) -> SkillsListResponse:
    service = SkillService(session)
    try:
        strategy, items = service.list_skills()
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc
    return SkillsListResponse(strategy=strategy, items=items)


@router.put("/skills/{skill_key}", response_model=SkillRead)
def update_skill(
    skill_key: str,
    payload: SkillUpdate,
    session: Session = Depends(get_session),
) -> SkillRead:
    service = SkillService(session)
    try:
        return service.update_skill(skill_key, payload)
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc
