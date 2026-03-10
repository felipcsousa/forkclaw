from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, select

from app.models.entities import (
    Agent,
    AgentProfile,
    AuditEvent,
    Setting,
    Task,
    TaskRun,
    ToolPermission,
    utc_now,
)


class OperationalSettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_default_agent(self) -> Agent | None:
        statement = (
            select(Agent)
            .where(Agent.is_default.is_(True))
            .order_by(Agent.created_at.asc())
        )
        return self.session.exec(statement).first()

    def get_profile(self, agent_id: str) -> AgentProfile | None:
        statement = select(AgentProfile).where(AgentProfile.agent_id == agent_id)
        return self.session.exec(statement).first()

    def list_settings(self) -> list[Setting]:
        statement = select(Setting).where(Setting.status == "active")
        return list(self.session.exec(statement))

    def get_setting(self, scope: str, key: str) -> Setting | None:
        statement = select(Setting).where(
            Setting.scope == scope,
            Setting.key == key,
            Setting.status == "active",
        )
        return self.session.exec(statement).first()

    def upsert_setting(
        self,
        *,
        scope: str,
        key: str,
        value_type: str,
        value_text: str | None = None,
        value_json: str | None = None,
    ) -> Setting:
        setting = self.get_setting(scope, key)
        if setting is None:
            setting = Setting(
                scope=scope,
                key=key,
                value_type=value_type,
                value_text=value_text,
                value_json=value_json,
                status="active",
            )
        else:
            setting.value_type = value_type
            setting.value_text = value_text
            setting.value_json = value_json
            setting.status = "active"
            setting.updated_at = utc_now()

        self.session.add(setting)
        self.session.commit()
        self.session.refresh(setting)
        return setting

    def save_profile(self, profile: AgentProfile) -> AgentProfile:
        profile.updated_at = utc_now()
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def update_workspace_permissions(self, agent_id: str, workspace_path: str) -> None:
        statement = select(ToolPermission).where(
            ToolPermission.agent_id == agent_id,
            ToolPermission.status == "active",
        )
        permissions = list(self.session.exec(statement))
        for permission in permissions:
            if permission.tool_name.startswith(("list_", "read_", "write_", "edit_")):
                permission.workspace_path = workspace_path
                permission.updated_at = utc_now()
                self.session.add(permission)
        self.session.commit()

    def sum_estimated_cost_since(self, agent_id: str, since: datetime) -> float:
        statement = (
            select(TaskRun.estimated_cost_usd)
            .join(Task, Task.id == TaskRun.task_id)
            .where(
                Task.agent_id == agent_id,
                TaskRun.finished_at.is_not(None),
                TaskRun.finished_at >= since,
                TaskRun.estimated_cost_usd.is_not(None),
            )
        )
        values = [value for value in self.session.exec(statement) if value is not None]
        return float(sum(values))

    def record_audit_event(
        self,
        *,
        agent_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, object],
        level: str = "info",
        summary_text: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            agent_id=agent_id,
            actor_type="system",
            level=level,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            summary_text=summary_text,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event
