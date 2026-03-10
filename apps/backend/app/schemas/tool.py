from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)

PermissionLevel = Literal["deny", "ask", "allow"]


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


class ToolCallsResponse(BaseModel):
    items: list[ToolCallRead]
