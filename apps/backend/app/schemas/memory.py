from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
    agent_id: str | None = None
    scope_type: str
    scope_key: str
    conversation_id: str | None
    session_id: str | None
    root_session_id: str | None = None
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
    workspace_path: str | None = None
    user_scope_key: str | None = None
    expires_at: datetime | None
    redaction_state: str
    security_state: str
    hidden_from_recall: bool
    deleted_at: datetime | None
    origin_message_id: str | None = None
    origin_task_run_id: str | None = None
    override_target_entry_id: str | None = None


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


MemoryScopeName = Literal[
    "current_conversation",
    "current_session_tree",
    "agent",
    "user",
    "workspace",
]
MemoryRecordType = Literal["memory_entry", "session_summary"]
MemoryOverrideStatus = Literal["none", "overrides_automatic", "overridden_by_manual"]


class MemoryScopeContextRead(BaseModel):
    agent_id: str | None
    session_id: str | None
    root_session_id: str | None
    workspace_path: str | None
    user_scope_key: str | None


class MemoryScopeSupportRead(BaseModel):
    name: MemoryScopeName
    available: bool


class MemoryOriginRead(BaseModel):
    table: str
    agent_id: str | None
    session_id: str | None
    root_session_id: str | None
    origin_message_id: str | None
    origin_task_run_id: str | None
    workspace_path: str | None
    matched_scopes: list[MemoryScopeName] = Field(default_factory=list)


class MemoryOverrideRead(BaseModel):
    status: MemoryOverrideStatus
    target_id: str | None = None
    effective_id: str | None = None
    selected_via_substitution: bool = False


class MemoryItemRead(BaseModel):
    record_type: MemoryRecordType
    id: str
    summary: str | None
    body: str | None
    source_kind: str
    importance: float
    score: float
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    origin: MemoryOriginRead
    override: MemoryOverrideRead


class MemorySearchResponse(BaseModel):
    query: str
    normalized_query: str
    applied_scopes: list[MemoryScopeName]
    context: MemoryScopeContextRead
    items: list[MemoryItemRead]


class MemoryRecallPreviewResponse(MemorySearchResponse):
    run_id: str | None = None


class MemoryScopesResponse(BaseModel):
    context: MemoryScopeContextRead
    default_scopes: list[MemoryScopeName]
    supported_scopes: list[MemoryScopeSupportRead]
