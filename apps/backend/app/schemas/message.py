from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.session import SessionRead


class SessionMessageCreate(BaseModel):
    content: str


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    conversation_id: str
    role: str
    status: str
    sequence_number: int
    content_text: str
    created_at: datetime
    updated_at: datetime


class SessionMessagesResponse(BaseModel):
    session: SessionRead
    items: list[MessageRead]
    has_more: bool | None = None
    next_before_sequence: int | None = None
