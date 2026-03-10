from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AgentExecutionCreate(BaseModel):
    message: str
    session_id: str | None = None
    title: str | None = None


class AgentExecutionResponse(BaseModel):
    task_id: str
    task_run_id: str
    session_id: str
    user_message_id: str
    assistant_message_id: str
    status: str
    output_text: str
    kernel_name: str
    model_name: str | None
    tools_used: list[str]
    finished_at: datetime | None
