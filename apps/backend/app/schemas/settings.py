from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: str
    key: str
    value_type: str
    value_text: str | None
    value_json: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class SettingsListResponse(BaseModel):
    items: list[SettingRead]
