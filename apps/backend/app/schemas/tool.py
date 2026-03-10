from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.schemas.skill import SkillSummaryRead

PermissionLevel = Literal["deny", "ask", "allow"]
ToolRisk = Literal["low", "medium", "high"]
ToolStatus = Literal["enabled", "experimental", "disabled"]
ToolPolicyProfileId = Literal["minimal", "coding", "research", "full"]


class ToolPermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    tool_name: str
    workspace_path: str | None
    permission_level: PermissionLevel
    approval_required: bool
    status: str
    created_at: datetime
    updated_at: datetime


class ToolPermissionUpdate(BaseModel):
    permission_level: PermissionLevel


class ToolPermissionsResponse(BaseModel):
    workspace_root: str
    items: list[ToolPermissionRead]


class ToolCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str | None
    message_id: str | None
    task_run_id: str | None
    tool_name: str
    status: str
    input_json: str | None
    output_json: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    guided_by_skills: list[SkillSummaryRead] = Field(default_factory=list)


class ToolCallsResponse(BaseModel):
    items: list[ToolCallRead]


class ToolCatalogEntryRead(BaseModel):
    id: str
    label: str
    description: str
    group: str
    group_label: str
    risk: ToolRisk
    status: ToolStatus
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    requires_workspace: bool


class ToolCatalogResponse(BaseModel):
    items: list[ToolCatalogEntryRead]


class ToolPolicyProfileRead(BaseModel):
    id: ToolPolicyProfileId
    label: str
    description: str
    defaults: dict[str, PermissionLevel]


class ToolPolicyOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    tool_name: str
    permission_level: PermissionLevel
    status: str
    created_at: datetime
    updated_at: datetime


class ToolPolicyRead(BaseModel):
    profile_id: ToolPolicyProfileId
    profiles: list[ToolPolicyProfileRead]
    overrides: list[ToolPolicyOverrideRead]


class ToolPolicyUpdate(BaseModel):
    profile_id: ToolPolicyProfileId
