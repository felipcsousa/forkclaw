from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, select

from app.models.entities import AcpSession, Message, SessionRecord, Setting, utc_now


class AcpRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_session_mapping(
        self,
        *,
        session_key: str,
        label: str,
        runtime: str,
        status: str,
        parent_session_id: str | None,
        backend_session_id: str | None,
        child_session_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> AcpSession:
        record = AcpSession(
            session_key=session_key,
            label=label,
            runtime=runtime,
            status=status,
            parent_session_id=parent_session_id,
            backend_session_id=backend_session_id,
            child_session_id=child_session_id,
            metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_mapping_by_key(self, session_key: str) -> AcpSession | None:
        statement = select(AcpSession).where(AcpSession.session_key == session_key)
        return self.session.exec(statement).first()

    def list_mappings(self, *, statuses: Sequence[str] | None = None) -> list[AcpSession]:
        statement = select(AcpSession)
        if statuses:
            statement = statement.where(AcpSession.status.in_(list(statuses)))
        statement = statement.order_by(AcpSession.created_at.desc())
        return list(self.session.exec(statement))

    def save_mapping(self, record: AcpSession) -> AcpSession:
        record.updated_at = utc_now()
        self.session.add(record)
        self.session.flush()
        return record

    def touch_prompt(self, record: AcpSession) -> AcpSession:
        now = utc_now()
        record.last_prompt_at = now
        record.updated_at = now
        self.session.add(record)
        self.session.flush()
        return record

    def get_session(self, session_id: str) -> SessionRecord | None:
        statement = select(SessionRecord).where(SessionRecord.id == session_id)
        return self.session.exec(statement).first()

    def list_messages_for_session(self, session_id: str, *, limit: int = 20) -> list[Message]:
        session_record = self.get_session(session_id)
        if session_record is None:
            return []
        statement = (
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.conversation_id == session_record.conversation_id,
            )
            .order_by(Message.sequence_number.desc())
            .limit(limit)
        )
        rows = list(self.session.exec(statement))
        rows.reverse()
        return rows

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
        value_text: str | None,
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
        self.session.flush()
        return setting
