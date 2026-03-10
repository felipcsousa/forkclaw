from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.approval import ApprovalActionResponse, ApprovalRead, ApprovalsResponse
from app.services.approvals import ApprovalService

router = APIRouter(tags=["approvals"])


@router.get("/approvals", response_model=ApprovalsResponse)
def list_approvals(session: Session = Depends(get_session)) -> ApprovalsResponse:
    service = ApprovalService(session)

    try:
        items = service.list_approvals()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ApprovalsResponse(items=items)


@router.get("/approvals/{approval_id}", response_model=ApprovalRead)
def get_approval(approval_id: str, session: Session = Depends(get_session)) -> ApprovalRead:
    service = ApprovalService(session)

    try:
        return service.get_approval(approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalActionResponse)
def approve_approval(
    approval_id: str,
    session: Session = Depends(get_session),
) -> ApprovalActionResponse:
    service = ApprovalService(session)

    try:
        return service.approve(approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/deny", response_model=ApprovalActionResponse)
def deny_approval(
    approval_id: str,
    session: Session = Depends(get_session),
) -> ApprovalActionResponse:
    service = ApprovalService(session)

    try:
        return service.deny(approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
