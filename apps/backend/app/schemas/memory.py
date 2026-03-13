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


class MemoryEntryHistoryResponse(BaseModel):
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
MemorySearchRecordType = Literal["memory_entry", "session_summary"]
MemorySearchOverrideStatus = Literal["none", "overrides_automatic", "overridden_by_manual"]


class MemoryScopeContextRead(BaseModel):
    agent_id: str | None
    session_id: str | None
    root_session_id: str | None
    workspace_path: str | None
    user_scope_key: str | None


class MemoryScopeSupportRead(BaseModel):
    name: MemoryScopeName
    available: bool


class MemorySearchOriginRead(BaseModel):
    table: str
    agent_id: str | None
    session_id: str | None
    root_session_id: str | None
    origin_message_id: str | None
    origin_task_run_id: str | None
    workspace_path: str | None
    scope_type: str | None = None
    scope_key: str | None = None
    matched_scopes: list[MemoryScopeName] = Field(default_factory=list)


class MemorySearchOverrideRead(BaseModel):
    status: MemorySearchOverrideStatus
    target_id: str | None = None
    effective_id: str | None = None
    selected_via_substitution: bool = False


class MemorySearchItemRead(BaseModel):
    record_type: MemorySearchRecordType
    id: str
    title: str | None = None
    summary: str | None
    body: str | None
    source_kind: str
    importance: float
    score: float
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    origin: MemorySearchOriginRead
    override: MemorySearchOverrideRead


class MemorySearchResponse(BaseModel):
    query: str
    normalized_query: str
    applied_scopes: list[MemoryScopeName]
    context: MemoryScopeContextRead
    items: list[MemorySearchItemRead]


class MemoryRecallPreviewResponse(MemorySearchResponse):
    run_id: str | None = None


class MemoryScopesResponse(BaseModel):
    context: MemoryScopeContextRead
    default_scopes: list[MemoryScopeName]
    supported_scopes: list[MemoryScopeSupportRead]


MemoryKind = Literal["stable", "episodic", "session_summary"]
MemoryImportance = Literal["low", "medium", "high"]
MemoryState = Literal["active", "deleted"]
MemoryRecallStatus = Literal["active", "hidden"]
MemoryListStateFilter = Literal["active", "hidden", "deleted"]
MemoryMode = Literal["all", "manual", "automatic"]


class MemoryItemRead(BaseModel):
    id: str
    kind: MemoryKind
    title: str
    content: str
    scope: str
    source_kind: str
    source_label: str
    importance: MemoryImportance
    state: MemoryState
    recall_status: MemoryRecallStatus
    is_manual: bool
    is_override: bool
    origin_session_id: str | None = None
    origin_subagent_session_id: str | None = None
    original_memory_id: str | None = None
    created_at: datetime
    updated_at: datetime


class MemoryItemCreate(BaseModel):
    kind: MemoryKind
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    scope: str = Field(default="global", min_length=1, max_length=100)
    importance: MemoryImportance = "medium"


class MemoryItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)
    scope: str | None = Field(default=None, min_length=1, max_length=100)
    importance: MemoryImportance | None = None


class MemoryItemsResponse(BaseModel):
    items: list[MemoryItemRead]


class MemoryHistoryEntryRead(BaseModel):
    id: str
    memory_id: str
    action: str
    summary: str | None = None
    snapshot: dict[str, object] | None = None
    created_at: datetime


class MemoryItemHistoryResponse(BaseModel):
    items: list[MemoryHistoryEntryRead]


class MemoryRecallItemRead(BaseModel):
    memory_id: str
    title: str
    kind: MemoryKind
    scope: str
    source_kind: str
    source_label: str
    importance: MemoryImportance
    reason: str
    origin_session_id: str | None = None
    origin_subagent_session_id: str | None = None


class MemoryRecallDetailRead(BaseModel):
    assistant_message_id: str
    session_id: str
    created_at: datetime
    reason_summary: str | None = None
    items: list[MemoryRecallItemRead]


class MemoryRecallLogEntryRead(MemoryRecallDetailRead):
    id: str
    task_run_id: str | None = None


class MemoryRecallLogResponse(BaseModel):
    items: list[MemoryRecallLogEntryRead]


class SessionRecallSummaryRead(BaseModel):
    assistant_message_id: str
    created_at: datetime
    recalled_count: int
    reason_summary: str | None = None
    items: list[MemoryRecallItemRead]


class SessionRecallSummariesResponse(BaseModel):
    items: list[SessionRecallSummaryRead]
