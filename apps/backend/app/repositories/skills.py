from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.entities import Agent, AuditEvent, Setting, utc_now


class SkillsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_default_agent(self) -> Agent | None:
        statement = select(Agent).where(Agent.is_default.is_(True)).order_by(Agent.created_at.asc())
        return self.session.exec(statement).first()

    def get_setting(self, scope: str, key: str) -> Setting | None:
        statement = select(Setting).where(
            Setting.scope == scope,
            Setting.key == key,
            Setting.status == "active",
        )
        return self.session.exec(statement).first()

    def list_settings_by_scope_prefix(self, prefix: str) -> list[Setting]:
        statement = (
            select(Setting)
            .where(Setting.scope.startswith(prefix), Setting.status == "active")
            .order_by(Setting.scope.asc(), Setting.key.asc())
        )
        return list(self.session.exec(statement))

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
