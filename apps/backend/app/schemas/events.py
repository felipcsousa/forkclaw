from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ExecutionEventType = Literal[
    "execution.started",
    "message.user.accepted",
    "assistant.run.created",
    "tool.started",
    "tool.completed",
    "tool.failed",
    "approval.requested",
    "subagent.spawned",
    "message.completed",
    "execution.completed",
    "execution.failed",
]


class EventMessagePayload(BaseModel):
    id: str
    role: str
    content_text: str
    sequence_number: int


class MessageUserAcceptedData(BaseModel):
    message: EventMessagePayload


class AssistantRunCreatedData(BaseModel):
    user_message_id: str | None = None
    status: str


class ToolEventData(BaseModel):
    tool_call_id: str
    tool_name: str
    status: str
    output_text: str | None = None
    error_message: str | None = None


class ApprovalRequestedData(BaseModel):
    approval_id: str
    tool_call_id: str | None = None
    tool_name: str | None = None
    requested_action: str
    reason: str | None = None
    status: str


class SubagentSpawnedData(BaseModel):
    parent_session_id: str
    child_session_id: str
    status: str | None = None
    goal_summary: str | None = None


class MessageCompletedData(BaseModel):
    message: EventMessagePayload


class ExecutionStateData(BaseModel):
    status: str
    error_message: str | None = None


class ExecutionEventEnvelope(BaseModel):
    id: str
    type: ExecutionEventType
    created_at: datetime
    session_id: str
    task_id: str | None = None
    task_run_id: str | None = None
    data: (
        MessageUserAcceptedData
        | AssistantRunCreatedData
        | ToolEventData
        | ApprovalRequestedData
        | SubagentSpawnedData
        | MessageCompletedData
        | ExecutionStateData
    )
