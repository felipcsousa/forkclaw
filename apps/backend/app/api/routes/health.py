from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(session: Session = Depends(get_session)) -> HealthResponse:
    session.exec(text("SELECT 1"))
    return HealthResponse(status="ok", service="backend", version="0.1.0")
