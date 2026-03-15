from __future__ import annotations

from pydantic import BaseModel


class ShutdownResponse(BaseModel):
    status: str
