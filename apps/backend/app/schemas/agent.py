from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    persona: str
    system_prompt: str | None
    identity_text: str
    soul_text: str
    user_context_text: str
    policy_base_text: str
    model_provider: str | None
    model_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    description: str | None
    status: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
    profile: AgentProfileRead | None


class AgentConfigUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    identity_text: str = Field(min_length=1, max_length=8000)
    soul_text: str = Field(min_length=1, max_length=8000)
    user_context_text: str = Field(default="", max_length=8000)
    policy_base_text: str = Field(min_length=1, max_length=8000)
    model_name: str = Field(min_length=1, max_length=100)
