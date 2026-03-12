from __future__ import annotations

from sqlmodel import Session

from app.models.entities import Agent, AgentProfile, Message, SessionRecord, Setting
from app.repositories.agent_os import AgentRepository, SessionRepository, SettingsRepository


class AgentOSService:
    def __init__(self, session: Session):
        self.session = session
        self.agents = AgentRepository(session)
        self.sessions = SessionRepository(session)
        self.settings = SettingsRepository(session)

    def get_default_agent_bundle(self) -> tuple[Agent | None, AgentProfile | None]:
        agent = self.agents.get_default_agent()
        if agent is None:
            return None, None

        profile = self.agents.get_profile(agent.id)
        return agent, profile

    def list_sessions(self) -> list[SessionRecord]:
        return self.sessions.list_sessions()

    def create_session(self, title: str | None) -> SessionRecord:
        agent = self.agents.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        normalized_title = (title or "").strip() or "New Session"
        return self.sessions.create_session(agent.id, normalized_title)

    def get_session(self, session_id: str) -> SessionRecord | None:
        return self.sessions.get_session(session_id)

    def list_session_messages(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before_sequence: int | None = None,
    ) -> tuple[SessionRecord | None, list[Message], bool | None, int | None]:
        record = self.sessions.get_session(session_id)
        if record is None:
            return None, [], None, None

        messages, has_more, next_before_sequence = self.sessions.list_messages(
            session_id,
            limit=limit,
            before_sequence=before_sequence,
        )
        return (
            record,
            messages,
            has_more if limit is not None else None,
            next_before_sequence if limit is not None else None,
        )

    def list_settings(self) -> list[Setting]:
        return self.settings.list_settings()
