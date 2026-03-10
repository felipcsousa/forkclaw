from __future__ import annotations

from sqlmodel import Session

from app.core.agent_profile_defaults import DEFAULT_AGENT_PROFILE, summarize_persona
from app.models.entities import Agent, AgentProfile
from app.repositories.agent_profile import AgentProfileRepository
from app.schemas.agent import AgentConfigUpdate


class AgentProfileService:
    def __init__(self, session: Session):
        self.repository = AgentProfileRepository(session)

    def get_default_agent_bundle(self) -> tuple[Agent | None, AgentProfile | None]:
        agent = self.repository.get_default_agent()
        if agent is None:
            return None, None

        return agent, self.repository.get_profile(agent.id)

    def update_default_agent_config(
        self,
        payload: AgentConfigUpdate,
    ) -> tuple[Agent, AgentProfile]:
        agent, profile = self._require_default_bundle()

        agent.name = payload.name.strip()
        agent.description = payload.description.strip() or None

        profile.display_name = agent.name
        profile.identity_text = payload.identity_text.strip()
        profile.soul_text = payload.soul_text.strip()
        profile.user_context_text = payload.user_context_text.strip()
        profile.policy_base_text = payload.policy_base_text.strip()
        profile.model_name = payload.model_name.strip()
        profile.persona = summarize_persona(profile.soul_text)
        profile.system_prompt = profile.soul_text

        saved_agent, saved_profile = self.repository.save_bundle(agent, profile)
        self.repository.record_audit_event(
            agent_id=saved_agent.id,
            event_type="agent.profile.updated",
            payload={"model_name": saved_profile.model_name or ""},
        )
        return saved_agent, saved_profile

    def reset_default_agent_config(self) -> tuple[Agent, AgentProfile]:
        agent, profile = self._require_default_bundle()

        agent.name = DEFAULT_AGENT_PROFILE.name
        agent.description = DEFAULT_AGENT_PROFILE.description

        profile.display_name = DEFAULT_AGENT_PROFILE.display_name
        profile.identity_text = DEFAULT_AGENT_PROFILE.identity_text
        profile.soul_text = DEFAULT_AGENT_PROFILE.soul_text
        profile.user_context_text = DEFAULT_AGENT_PROFILE.user_context_text
        profile.policy_base_text = DEFAULT_AGENT_PROFILE.policy_base_text
        profile.model_provider = DEFAULT_AGENT_PROFILE.model_provider
        profile.model_name = DEFAULT_AGENT_PROFILE.model_name
        profile.persona = summarize_persona(profile.soul_text)
        profile.system_prompt = profile.soul_text

        saved_agent, saved_profile = self.repository.save_bundle(agent, profile)
        self.repository.record_audit_event(
            agent_id=saved_agent.id,
            event_type="agent.profile.reset",
            payload={"model_name": saved_profile.model_name or ""},
        )
        return saved_agent, saved_profile

    def _require_default_bundle(self) -> tuple[Agent, AgentProfile]:
        agent, profile = self.get_default_agent_bundle()

        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)
        if profile is None:
            msg = "Agent profile not found."
            raise ValueError(msg)

        return agent, profile
