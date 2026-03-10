from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SkillOrigin = Literal["bundled", "user-local", "workspace"]


class SkillRead(BaseModel):
    key: str
    name: str
    description: str
    origin: SkillOrigin
    enabled: bool
    eligible: bool
    selected: bool
    blocked_reasons: list[str]
    config: dict[str, Any] | None = None
    configured_env_keys: list[str] = Field(default_factory=list)
    primary_env: str | None = None


class SkillSummaryRead(BaseModel):
    key: str
    name: str
    origin: SkillOrigin
    source_path: str
    selected: bool
    eligible: bool
    blocked_reasons: list[str] = Field(default_factory=list)


class SkillsListResponse(BaseModel):
    strategy: str
    items: list[SkillRead]


class SkillUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None
    env: dict[str, str] | None = None
    clear_env: list[str] = Field(default_factory=list)
    api_key: str | None = Field(default=None, max_length=4000)
    clear_api_key: bool = False
