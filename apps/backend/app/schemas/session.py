from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    title: str | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    title: str
    summary: str | None
    status: str
    started_at: datetime
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SessionsListResponse(BaseModel):
    items: list[SessionRead]
