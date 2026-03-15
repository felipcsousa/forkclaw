from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.schemas.internal import ShutdownResponse

router = APIRouter(tags=["internal"], include_in_schema=False)


@router.post(
    "/internal/shutdown",
    response_model=ShutdownResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_shutdown(request: Request) -> ShutdownResponse:
    callback = getattr(request.app.state, "shutdown_callback", None)
    if callable(callback):
        callback()
    return ShutdownResponse(status="accepted")
