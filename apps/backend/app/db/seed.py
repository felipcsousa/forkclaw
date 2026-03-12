from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.core.agent_profile_defaults import (
    DEFAULT_AGENT_PROFILE,
    LEGACY_AGENT_PROFILE,
    summarize_persona,
)
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.entities import (
    Agent,
    AgentProfile,
    AuditEvent,
    Setting,
    ToolPermission,
    ToolPolicyOverride,
    utc_now,
)
from app.tools.catalog import build_tool_catalog
from app.tools.policies import get_tool_policy_profile, resolve_effective_permission_level


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
        if not existing_agent.name or existing_agent.name == LEGACY_AGENT_PROFILE.name:
            existing_agent.name = DEFAULT_AGENT_PROFILE.name
        if (
            not existing_agent.description
            or existing_agent.description == LEGACY_AGENT_PROFILE.description
        ):
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
        if not profile.display_name or profile.display_name == LEGACY_AGENT_PROFILE.display_name:
            profile.display_name = DEFAULT_AGENT_PROFILE.display_name
        if not profile.identity_text or profile.identity_text == LEGACY_AGENT_PROFILE.identity_text:
            profile.identity_text = DEFAULT_AGENT_PROFILE.identity_text
        if not profile.soul_text or profile.soul_text == LEGACY_AGENT_PROFILE.soul_text:
            profile.soul_text = DEFAULT_AGENT_PROFILE.soul_text
        if (
            profile.user_context_text is None
            or profile.user_context_text == LEGACY_AGENT_PROFILE.user_context_text
        ):
            profile.user_context_text = DEFAULT_AGENT_PROFILE.user_context_text
        if (
            not profile.policy_base_text
            or profile.policy_base_text == LEGACY_AGENT_PROFILE.policy_base_text
        ):
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
        (
            "runtime",
            "heartbeat_interval_seconds",
        ): ("integer", str(settings.default_heartbeat_interval_seconds)),
        (
            "runtime",
            "shell_exec_max_timeout_seconds",
        ): ("float", f"{settings.shell_exec_max_timeout_seconds:.6f}"),
        (
            "runtime",
            "shell_exec_max_output_chars",
        ): ("integer", str(settings.shell_exec_max_output_chars)),
        (
            "runtime",
            "shell_exec_allowed_cwd_roots",
        ): ("json", None),
        (
            "runtime",
            "shell_exec_allowed_env_keys",
        ): ("json", None),
        ("budget", "daily_usd"): ("float", f"{settings.default_daily_budget_usd:.6f}"),
        ("budget", "monthly_usd"): ("float", f"{settings.default_monthly_budget_usd:.6f}"),
        ("preferences", "default_view"): ("string", settings.default_app_view),
        (
            "preferences",
            "activity_poll_seconds",
        ): ("integer", str(settings.default_activity_poll_seconds)),
        ("tools", "policy_profile"): ("string", "minimal"),
    }

    created_settings: set[tuple[str, str]] = set()
    for (scope, key), (value_type, value_text) in defaults.items():
        existing_setting = session.exec(
            select(Setting).where(Setting.scope == scope, Setting.key == key)
        ).first()
        if existing_setting is None:
            created_settings.add((scope, key))
            value_json = None
            if (scope, key) == ("runtime", "shell_exec_allowed_cwd_roots"):
                allowed_roots = [
                    str(Path(item).expanduser().resolve())
                    for item in settings.shell_exec_allowed_cwd_roots
                ]
                value_json = json.dumps(
                    allowed_roots,
                    ensure_ascii=False,
                )
            elif (scope, key) == ("runtime", "shell_exec_allowed_env_keys"):
                value_json = json.dumps(
                    list(settings.shell_exec_allowed_env_keys),
                    ensure_ascii=False,
                )
            session.add(
                Setting(
                    scope=scope,
                    key=key,
                    value_type=value_type,
                    value_text=value_text,
                    value_json=value_json,
                    status="active",
                )
            )

    existing_permissions = {
        item.tool_name: item
        for item in session.exec(
            select(ToolPermission).where(
                ToolPermission.agent_id == existing_agent.id,
                ToolPermission.status == "active",
            )
        )
    }

    active_profile_setting = session.exec(
        select(Setting).where(Setting.scope == "tools", Setting.key == "policy_profile")
    ).first()
    profile_id = (
        active_profile_setting.value_text
        if active_profile_setting and active_profile_setting.value_text
        else "minimal"
    )
    try:
        profile_id = get_tool_policy_profile(profile_id).id
    except ValueError:
        profile_id = "minimal"

    catalog = build_tool_catalog()
    existing_overrides = {
        item.tool_name: item
        for item in session.exec(
            select(ToolPolicyOverride).where(
                ToolPolicyOverride.agent_id == existing_agent.id,
                ToolPolicyOverride.status == "active",
            )
        )
    }

    if ("tools", "policy_profile") in created_settings:
        for item in catalog:
            existing_permission = existing_permissions.get(item.id)
            if existing_permission is None or item.id in existing_overrides:
                continue

            default_level = resolve_effective_permission_level(
                profile_id="minimal",
                tool_group=item.group,
                override_level=None,
            )
            if existing_permission.permission_level == default_level:
                continue

            override = ToolPolicyOverride(
                agent_id=existing_agent.id,
                tool_name=item.id,
                permission_level=existing_permission.permission_level,
                status="active",
            )
            session.add(override)
            existing_overrides[item.id] = override

    workspace_root_setting = session.exec(
        select(Setting).where(Setting.scope == "security", Setting.key == "workspace_root")
    ).first()
    workspace_root = (
        workspace_root_setting.value_text
        if workspace_root_setting and workspace_root_setting.value_text
        else str(settings.default_workspace_root)
    )
    for item in catalog:
        effective_level = resolve_effective_permission_level(
            profile_id=profile_id,
            tool_group=item.group,
            override_level=(
                existing_overrides[item.id].permission_level
                if item.id in existing_overrides
                else None
            ),
        )
        existing_permission = existing_permissions.get(item.id)
        if existing_permission is None:
            existing_permission = ToolPermission(
                agent_id=existing_agent.id,
                tool_name=item.id,
                workspace_path=workspace_root if item.requires_workspace else None,
                permission_level=effective_level,
                approval_required=effective_level == "ask",
                status="active",
            )
        else:
            existing_permission.workspace_path = workspace_root if item.requires_workspace else None
            existing_permission.permission_level = effective_level
            existing_permission.approval_required = effective_level == "ask"
            existing_permission.status = "active"
            existing_permission.updated_at = utc_now()
        session.add(existing_permission)

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
