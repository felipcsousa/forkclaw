from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ApprovalRead(BaseModel):
    id: str
    agent_id: str
    task_id: str | None
    tool_call_id: str | None
    kind: str
    requested_action: str
    reason: str | None
    status: str
    decided_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    tool_name: str | None
    tool_input_json: str | None
    session_id: str | None
    session_title: str | None
    task_run_id: str | None


class ApprovalsResponse(BaseModel):
    items: list[ApprovalRead]


class ApprovalActionResponse(BaseModel):
    approval: ApprovalRead
    task_run_status: str
    tool_call_status: str
    output_text: str
    assistant_message_id: str | None
