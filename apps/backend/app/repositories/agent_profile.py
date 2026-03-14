from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.entities import Agent, AgentProfile, AuditEvent, utc_now


class AgentProfileRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_default_agent(self) -> Agent | None:
        statement = select(Agent).where(Agent.is_default.is_(True)).order_by(Agent.created_at.asc())
        return self.session.exec(statement).first()

    def get_profile(self, agent_id: str) -> AgentProfile | None:
        statement = select(AgentProfile).where(AgentProfile.agent_id == agent_id)
        return self.session.exec(statement).first()

    def save_bundle(self, agent: Agent, profile: AgentProfile) -> tuple[Agent, AgentProfile]:
        agent.updated_at = utc_now()
        profile.updated_at = utc_now()
        self.session.add(agent)
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(agent)
        self.session.refresh(profile)
        return agent, profile

    def record_audit_event(
        self,
        *,
        agent_id: str,
        event_type: str,
        payload: dict[str, str],
        level: str = "info",
        summary_text: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            agent_id=agent_id,
            actor_type="system",
            level=level,
            event_type=event_type,
            entity_type="agent_profile",
            entity_id=agent_id,
            summary_text=summary_text,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event
