from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.provider_catalog import normalize_provider_id

ProviderName = Literal[
    "product_echo",
    "openai",
    "anthropic",
    "openrouter",
    "deepseek",
    "gemini",
    "kimi-coding",
]

AppViewName = Literal[
    "chat",
    "profile",
    "settings",
    "tools",
    "approvals",
    "jobs",
    "activity",
]


class OperationalSettingsRead(BaseModel):
    provider: ProviderName
    model_name: str
    workspace_root: str
    max_iterations_per_execution: int
    daily_budget_usd: float
    monthly_budget_usd: float
    default_view: AppViewName
    activity_poll_seconds: int
    provider_api_key_configured: bool


class OperationalSettingsUpdate(BaseModel):
    provider: ProviderName
    model_name: str = Field(min_length=1, max_length=200)
    workspace_root: str = Field(min_length=1, max_length=4000)
    max_iterations_per_execution: int = Field(ge=1, le=10)
    daily_budget_usd: float = Field(gt=0, le=1_000_000)
    monthly_budget_usd: float = Field(gt=0, le=10_000_000)
    default_view: AppViewName
    activity_poll_seconds: int = Field(ge=1, le=300)
    api_key: str | None = Field(default=None, max_length=4000)
    clear_api_key: bool = False

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider_id(value)
