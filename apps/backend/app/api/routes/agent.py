from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.errors import value_error_as_http_exception
from app.db.session import get_session
from app.models.entities import Agent, AgentProfile
from app.schemas.agent import AgentConfigUpdate, AgentProfileRead, AgentRead
from app.services.agent_profile import AgentProfileService

router = APIRouter(tags=["agent"])


def serialize_agent(agent: Agent, profile: AgentProfile | None) -> AgentRead:
    return AgentRead(
        id=agent.id,
        slug=agent.slug,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        is_default=agent.is_default,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        profile=(
            AgentProfileRead(
                id=profile.id,
                display_name=profile.display_name,
                persona=profile.persona,
                system_prompt=profile.system_prompt,
                identity_text=profile.identity_text,
                soul_text=profile.soul_text,
                user_context_text=profile.user_context_text,
                policy_base_text=profile.policy_base_text,
                model_provider=profile.model_provider,
                model_name=profile.model_name,
                status=profile.status,
                created_at=profile.created_at,
                updated_at=profile.updated_at,
            )
            if profile is not None
            else None
        ),
    )


@router.get("/agent", response_model=AgentRead)
def get_default_agent(session: Session = Depends(get_session)) -> AgentRead:
    service = AgentProfileService(session)
    agent, profile = service.get_default_agent_bundle()

    if agent is None:
        raise HTTPException(status_code=404, detail="Default agent not found.")

    return serialize_agent(agent, profile)


@router.get("/agent/config", response_model=AgentRead)
def get_agent_config(session: Session = Depends(get_session)) -> AgentRead:
    return get_default_agent(session)


@router.put("/agent/config", response_model=AgentRead)
def update_agent_config(
    payload: AgentConfigUpdate,
    session: Session = Depends(get_session),
) -> AgentRead:
    service = AgentProfileService(session)

    try:
        agent, profile = service.update_default_agent_config(payload)
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc

    return serialize_agent(agent, profile)


@router.post("/agent/config/reset", response_model=AgentRead)
def reset_agent_config(session: Session = Depends(get_session)) -> AgentRead:
    service = AgentProfileService(session)

    try:
        agent, profile = service.reset_default_agent_config()
    except ValueError as exc:
        raise value_error_as_http_exception(exc, default_status=404) from exc

    return serialize_agent(agent, profile)
