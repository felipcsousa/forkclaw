from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AcpBridgeStatusRead(BaseModel):
    enabled: bool


class AcpBridgeStatusUpdate(BaseModel):
    enabled: bool


class AcpSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_key: str
    label: str
    runtime: str
    status: str
    parent_session_id: str | None
    backend_session_id: str | None
    child_session_id: str | None
    last_prompt_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AcpSessionsListResponse(BaseModel):
    items: list[AcpSessionRead]


class AcpNewSessionRequest(BaseModel):
    label: str = Field(default="ACP Session", min_length=1, max_length=200)
    runtime: str = Field(default="acp", min_length=1, max_length=50)
    parent_session_id: str | None = None


class AcpNewSessionResponse(BaseModel):
    session_key: str
    mapping: AcpSessionRead


class AcpPromptRequest(BaseModel):
    session_key: str
    text: str = Field(min_length=1)


class AcpPromptResponse(BaseModel):
    session_key: str
    output_text: str
    session_id: str
    task_run_id: str
    assistant_message_id: str | None


class AcpCancelRequest(BaseModel):
    session_key: str


class AcpCancelResponse(BaseModel):
    session_key: str
    status: str


class AcpLoadSessionRequest(BaseModel):
    session_key: str
    limit: int = Field(default=20, ge=1, le=200)


class AcpTranscriptMessageRead(BaseModel):
    id: str
    role: str
    sequence_number: int
    content_text: str
    created_at: datetime


class AcpLoadSessionResponse(BaseModel):
    session_key: str
    session_id: str
    messages: list[AcpTranscriptMessageRead]
