from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.api.errors import value_error_as_http_exception
from app.db.session import get_session
from app.schemas.cron_job import (
    CronJobCreate,
    CronJobRead,
    CronJobsDashboardResponse,
    CronJobUpdate,
)
from app.services.cron_jobs import CronJobService

router = APIRouter(tags=["cron-jobs"])


@router.get("/cron-jobs", response_model=CronJobsDashboardResponse)
def get_cron_jobs_dashboard(
    session: Session = Depends(get_session),
) -> CronJobsDashboardResponse:
    service = CronJobService(session)
    try:
        return service.get_dashboard()
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc


@router.post("/cron-jobs", response_model=CronJobRead, status_code=status.HTTP_201_CREATED)
def create_cron_job(
    payload: CronJobCreate,
    session: Session = Depends(get_session),
) -> CronJobRead:
    service = CronJobService(session)
    try:
        return service.create_job(payload)
    except ValueError as exc:
        raise value_error_as_http_exception(exc) from exc


@router.patch("/cron-jobs/{job_id}", response_model=CronJobRead)
def update_cron_job(
    job_id: str,
    payload: CronJobUpdate,
    session: Session = Depends(get_session),
) -> CronJobRead:
    service = CronJobService(session)
    try:
        return service.update_job(job_id, payload)
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc


@router.post("/cron-jobs/{job_id}/pause", response_model=CronJobRead)
def pause_cron_job(
    job_id: str,
    session: Session = Depends(get_session),
) -> CronJobRead:
    service = CronJobService(session)
    try:
        return service.pause_job(job_id)
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc


@router.post("/cron-jobs/{job_id}/activate", response_model=CronJobRead)
def activate_cron_job(
    job_id: str,
    session: Session = Depends(get_session),
) -> CronJobRead:
    service = CronJobService(session)
    try:
        return service.activate_job(job_id)
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc


@router.delete("/cron-jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cron_job(job_id: str, session: Session = Depends(get_session)) -> Response:
    service = CronJobService(session)
    try:
        service.remove_job(job_id)
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
