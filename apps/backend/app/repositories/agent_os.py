from __future__ import annotations

from sqlmodel import Session, select

from app.models.entities import (
    Agent,
    AgentProfile,
    AuditEvent,
    Message,
    SessionRecord,
    Setting,
    generate_id,
    utc_now,
)


class AgentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_default_agent(self) -> Agent | None:
        statement = select(Agent).where(Agent.is_default.is_(True)).order_by(Agent.created_at.asc())
        return self.session.exec(statement).first()

    def get_profile(self, agent_id: str) -> AgentProfile | None:
        statement = select(AgentProfile).where(AgentProfile.agent_id == agent_id)
        return self.session.exec(statement).first()


class SessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_sessions(self) -> list[SessionRecord]:
        statement = (
            select(SessionRecord)
            .where(SessionRecord.kind == "main")
            .order_by(SessionRecord.updated_at.desc())
        )
        return list(self.session.exec(statement))

    def get_session(self, session_id: str) -> SessionRecord | None:
        statement = select(SessionRecord).where(SessionRecord.id == session_id)
        return self.session.exec(statement).first()

    def list_messages(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before_sequence: int | None = None,
    ) -> tuple[list[Message], bool, int | None]:
        session_record = self.get_session(session_id)
        if session_record is None:
            return [], False, None

        statement = select(Message).where(
            Message.session_id == session_id,
            Message.conversation_id == session_record.conversation_id,
        )
        if before_sequence is not None:
            statement = statement.where(Message.sequence_number < before_sequence)

        if limit is None:
            statement = statement.order_by(Message.sequence_number.asc())
            return list(self.session.exec(statement)), False, None

        rows = list(
            self.session.exec(statement.order_by(Message.sequence_number.desc()).limit(limit + 1))
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        page.reverse()
        next_before_sequence = page[0].sequence_number if has_more and page else None
        return page, has_more, next_before_sequence

    def create_session(self, agent_id: str, title: str) -> SessionRecord:
        record = SessionRecord(
            agent_id=agent_id,
            kind="main",
            title=title,
            status="active",
            root_session_id=None,
            spawn_depth=0,
            conversation_id=generate_id(),
            started_at=utc_now(),
        )
        record.root_session_id = record.id
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def reset_conversation(self, session_record: SessionRecord) -> SessionRecord:
        session_record.conversation_id = generate_id()
        session_record.summary = None
        session_record.last_message_at = None
        session_record.updated_at = utc_now()
        self.session.add(session_record)
        self.session.commit()
        self.session.refresh(session_record)
        return session_record

    def record_audit_event(
        self,
        *,
        agent_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str | None,
        payload_json: str | None = None,
        summary_text: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            agent_id=agent_id,
            actor_type="system",
            level="info",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            summary_text=summary_text,
            payload_json=payload_json,
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event


class SettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_settings(self) -> list[Setting]:
        statement = select(Setting).order_by(Setting.scope.asc(), Setting.key.asc())
        return list(self.session.exec(statement))
