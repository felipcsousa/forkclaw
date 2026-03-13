from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryEntryCreate(BaseModel):
    scope_type: str
    scope_key: str
    conversation_id: str | None = None
    session_id: str | None = None
    parent_session_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=12000)
    summary: str | None = Field(default=None, max_length=4000)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    expires_at: datetime | None = None

    @field_validator("scope_type", "scope_key", "title", "body", mode="before")
    @classmethod
    def _trim_required_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("summary", mode="before")
    @classmethod
    def _trim_optional_summary(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class MemoryEntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=12000)
    summary: str | None = Field(default=None, max_length=4000)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    expires_at: datetime | None = None

    @field_validator("title", "body", mode="before")
    @classmethod
    def _trim_optional_strings(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("summary", mode="before")
    @classmethod
    def _trim_summary(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class MemoryEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scope_type: str
    scope_key: str
    conversation_id: str | None
    session_id: str | None
    parent_session_id: str | None
    source_kind: str
    lifecycle_state: str
    title: str
    body: str
    summary: str | None
    importance: float
    confidence: float
    dedupe_hash: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    expires_at: datetime | None
    redaction_state: str
    security_state: str
    hidden_from_recall: bool
    deleted_at: datetime | None


class MemoryEntriesListResponse(BaseModel):
    items: list[MemoryEntryRead]


class MemoryHistoryItemRead(BaseModel):
    id: str
    memory_id: str
    action: str
    actor_type: str
    actor_id: str | None
    before_snapshot: dict[str, Any] | None
    after_snapshot: dict[str, Any] | None
    created_at: datetime


class MemoryHistoryResponse(BaseModel):
    items: list[MemoryHistoryItemRead]


class MemoryDeleteResponse(BaseModel):
    deleted: bool
