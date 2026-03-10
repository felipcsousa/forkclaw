from __future__ import annotations

import json

from sqlmodel import Session, select

from app.core.agent_profile_defaults import DEFAULT_AGENT_PROFILE, summarize_persona
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.entities import Agent, AgentProfile, AuditEvent, Setting, ToolPermission, utc_now


def seed_default_data(session: Session) -> Agent:
    settings = get_settings()
    existing_agent = session.exec(
        select(Agent).where(Agent.slug == settings.default_agent_slug)
    ).first()

    if existing_agent is None:
        existing_agent = Agent(
            slug=settings.default_agent_slug,
            name=DEFAULT_AGENT_PROFILE.name,
            description=DEFAULT_AGENT_PROFILE.description,
            status="active",
            is_default=True,
        )
        session.add(existing_agent)
        session.flush()
    else:
        if not existing_agent.name:
            existing_agent.name = DEFAULT_AGENT_PROFILE.name
        if not existing_agent.description:
            existing_agent.description = DEFAULT_AGENT_PROFILE.description

    profile = session.exec(
        select(AgentProfile).where(AgentProfile.agent_id == existing_agent.id)
    ).first()
    if profile is None:
        profile = AgentProfile(
            agent_id=existing_agent.id,
            display_name=DEFAULT_AGENT_PROFILE.display_name,
            persona=summarize_persona(DEFAULT_AGENT_PROFILE.soul_text),
            system_prompt=DEFAULT_AGENT_PROFILE.soul_text,
            identity_text=DEFAULT_AGENT_PROFILE.identity_text,
            soul_text=DEFAULT_AGENT_PROFILE.soul_text,
            user_context_text=DEFAULT_AGENT_PROFILE.user_context_text,
            policy_base_text=DEFAULT_AGENT_PROFILE.policy_base_text,
            model_provider=DEFAULT_AGENT_PROFILE.model_provider,
            model_name=DEFAULT_AGENT_PROFILE.model_name,
            status="active",
        )
        session.add(profile)
    else:
        if not profile.model_provider:
            profile.model_provider = DEFAULT_AGENT_PROFILE.model_provider
        if not profile.model_name:
            profile.model_name = DEFAULT_AGENT_PROFILE.model_name
        if not profile.display_name:
            profile.display_name = DEFAULT_AGENT_PROFILE.display_name
        if not profile.identity_text:
            profile.identity_text = DEFAULT_AGENT_PROFILE.identity_text
        if not profile.soul_text:
            profile.soul_text = DEFAULT_AGENT_PROFILE.soul_text
        if not profile.user_context_text:
            profile.user_context_text = DEFAULT_AGENT_PROFILE.user_context_text
        if not profile.policy_base_text:
            profile.policy_base_text = DEFAULT_AGENT_PROFILE.policy_base_text
        profile.persona = summarize_persona(profile.soul_text)
        profile.system_prompt = profile.soul_text

    defaults = {
        ("app", "default_agent_slug"): ("string", settings.default_agent_slug),
        ("app", "timezone"): ("string", settings.default_timezone),
        ("security", "approval_mode"): ("string", "explicit"),
        ("security", "workspace_root"): ("string", str(settings.default_workspace_root)),
        ("runtime", "default_model_provider"): ("string", settings.default_model_provider),
        ("runtime", "default_model_name"): ("string", settings.default_model_name),
        (
            "runtime",
            "max_iterations_per_execution",
        ): ("integer", str(settings.default_max_iterations_per_execution)),
        ("budget", "daily_usd"): ("float", f"{settings.default_daily_budget_usd:.6f}"),
        ("budget", "monthly_usd"): ("float", f"{settings.default_monthly_budget_usd:.6f}"),
        ("preferences", "default_view"): ("string", settings.default_app_view),
        (
            "preferences",
            "activity_poll_seconds",
        ): ("integer", str(settings.default_activity_poll_seconds)),
    }

    for (scope, key), (value_type, value_text) in defaults.items():
        existing_setting = session.exec(
            select(Setting).where(Setting.scope == scope, Setting.key == key)
        ).first()
        if existing_setting is None:
            session.add(
                Setting(
                    scope=scope,
                    key=key,
                    value_type=value_type,
                    value_text=value_text,
                    value_json=None,
                    status="active",
                )
            )

    tool_defaults = {
        "list_files": ("ask", True, str(settings.default_workspace_root)),
        "read_file": ("ask", True, str(settings.default_workspace_root)),
        "write_file": ("ask", True, str(settings.default_workspace_root)),
        "edit_file": ("ask", True, str(settings.default_workspace_root)),
        "clipboard_read": ("ask", True, None),
        "clipboard_write": ("ask", True, None),
    }

    for tool_name, (permission_level, approval_required, workspace_path) in tool_defaults.items():
        existing_permission = session.exec(
            select(ToolPermission).where(
                ToolPermission.agent_id == existing_agent.id,
                ToolPermission.tool_name == tool_name,
                ToolPermission.status == "active",
            )
        ).first()
        if existing_permission is None:
            session.add(
                ToolPermission(
                    agent_id=existing_agent.id,
                    tool_name=tool_name,
                    workspace_path=workspace_path,
                    permission_level=permission_level,
                    approval_required=approval_required,
                    status="active",
                )
            )

    seed_event = session.exec(
        select(AuditEvent).where(
            AuditEvent.event_type == "bootstrap.seed",
            AuditEvent.entity_type == "agent",
            AuditEvent.entity_id == existing_agent.id,
        )
    ).first()
    if seed_event is None:
        session.add(
            AuditEvent(
                agent_id=existing_agent.id,
                actor_type="system",
                event_type="bootstrap.seed",
                entity_type="agent",
                entity_id=existing_agent.id,
                payload_json=json.dumps({"seeded_at": utc_now().isoformat()}),
            )
        )

    session.commit()
    session.refresh(existing_agent)
    return existing_agent


def run_seed() -> None:
    with get_db_session() as session:
        seed_default_data(session)


if __name__ == "__main__":
    run_seed()
