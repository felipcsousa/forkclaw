from __future__ import annotations

from fastapi import APIRouter, Request, status

router = APIRouter(tags=["internal"], include_in_schema=False)


@router.post("/internal/shutdown", status_code=status.HTTP_202_ACCEPTED)
def request_shutdown(request: Request) -> dict[str, str]:
    callback = getattr(request.app.state, "shutdown_callback", None)
    if callable(callback):
        callback()
    return {"status": "accepted"}
