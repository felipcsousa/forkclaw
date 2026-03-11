from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from app.core.config import get_settings
from app.core.secrets import get_secret_store
from app.kernel.contracts import KernelSkill, KernelSkillResolution, KernelSkillSummary
from app.models.entities import ToolPermission
from app.repositories.skills import SkillsRepository
from app.schemas.skill import SkillRead, SkillUpdate
from app.skills.loader import SkillEntryConfig, resolve_skills


@dataclass(frozen=True)
class ExecutionSkillsBundle:
    strategy: str
    skills: list[KernelSkill]
    summaries: list[KernelSkillSummary]
    environment_overlay: dict[str, str]


class SkillService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = SkillsRepository(session)
        self.secret_store = get_secret_store()

    def list_skills(self) -> tuple[str, list[SkillRead]]:
        resolution = self._resolve_catalog()
        items = [
            self._to_read_model(item, configured_env_keys=self._configured_env_keys_for(item.key))
            for item in resolution.items
        ]
        return resolution.strategy, items

    def update_skill(self, skill_key: str, payload: SkillUpdate) -> SkillRead:
        resolution = self._resolve_catalog()
        by_key = {item.key: item for item in resolution.items}
        if skill_key not in by_key:
            msg = f"Unknown skill: {skill_key}"
            raise ValueError(msg)

        entry_scope = self._entry_scope(skill_key)
        if payload.enabled is not None:
            self.repository.upsert_setting(
                scope=entry_scope,
                key="enabled",
                value_type="boolean",
                value_text=str(payload.enabled).lower(),
            )
        if payload.config is not None:
            self.repository.upsert_setting(
                scope=entry_scope,
                key="config",
                value_type="json",
                value_json=self._json_dump(payload.config),
            )

        configured_env_keys = self._configured_env_keys_for(skill_key)
        if payload.env:
            for env_name, value in payload.env.items():
                if not value:
                    continue
                self.secret_store.set_skill_env_value(skill_key, env_name, value)
                configured_env_keys.add(env_name)

        primary_env = self._primary_env_for(by_key[skill_key].metadata)
        if payload.api_key:
            if not primary_env:
                msg = f"Skill `{skill_key}` does not declare metadata.forkclaw.primaryEnv."
                raise ValueError(msg)
            self.secret_store.set_skill_env_value(skill_key, primary_env, payload.api_key)
            configured_env_keys.add(primary_env)
        if payload.clear_api_key and primary_env:
            self.secret_store.delete_skill_env_value(skill_key, primary_env)
            configured_env_keys.discard(primary_env)

        for env_name in payload.clear_env:
            self.secret_store.delete_skill_env_value(skill_key, env_name)
            configured_env_keys.discard(env_name)

        if payload.env is not None or payload.api_key or payload.clear_api_key or payload.clear_env:
            self.repository.upsert_setting(
                scope=entry_scope,
                key="env_keys",
                value_type="json",
                value_json=self._json_dump(sorted(configured_env_keys)),
            )

        agent = self.repository.get_default_agent()
        if agent is not None:
            self.repository.record_audit_event(
                agent_id=agent.id,
                event_type="skills.config.updated",
                entity_type="skill",
                entity_id=skill_key,
                payload={
                    "skill_key": skill_key,
                    "enabled_updated": payload.enabled is not None,
                    "config_updated": payload.config is not None,
                    "env_keys": sorted(configured_env_keys),
                    "api_key_updated": bool(payload.api_key),
                    "api_key_cleared": payload.clear_api_key,
                },
                summary_text="Skill configuration updated.",
            )

        refreshed = self._resolve_catalog()
        item = next(item for item in refreshed.items if item.key == skill_key)
        configured_env_keys = self._configured_env_keys_for(skill_key)
        return self._to_read_model(
            item,
            configured_env_keys=configured_env_keys,
        )

    def build_execution_bundle(
        self,
        *,
        tool_permissions: list[ToolPermission],
    ) -> ExecutionSkillsBundle:
        resolution = self._resolve_catalog(tool_permissions=tool_permissions)
        skills = [
            KernelSkill(
                key=item.key,
                name=item.name,
                description=item.description,
                origin=item.origin,
                source_path=item.source_path,
                content=item.content,
                config=item.config,
            )
            for item in resolution.selected
        ]
        summaries = [
            KernelSkillSummary(
                key=item.key,
                name=item.name,
                origin=item.origin,
                source_path=item.source_path,
                selected=item.selected,
                eligible=item.eligible,
                blocked_reasons=item.blocked_reasons,
            )
            for item in resolution.items
        ]
        environment_overlay: dict[str, str] = {}
        config_by_key = self._load_entry_configs()
        for item in resolution.selected:
            environment_overlay.update(config_by_key.get(item.key, SkillEntryConfig()).env)
        return ExecutionSkillsBundle(
            strategy=resolution.strategy,
            skills=skills,
            summaries=summaries,
            environment_overlay=environment_overlay,
        )

    @staticmethod
    def serialize_bundle(bundle: ExecutionSkillsBundle) -> dict[str, object]:
        return {
            "strategy": bundle.strategy,
            "items": [
                {
                    "key": item.key,
                    "name": item.name,
                    "origin": item.origin,
                    "source_path": item.source_path,
                    "selected": item.selected,
                    "eligible": item.eligible,
                    "blocked_reasons": item.blocked_reasons,
                }
                for item in bundle.summaries
            ],
        }

    def _resolve_catalog(
        self,
        *,
        tool_permissions: list[ToolPermission] | None = None,
    ):
        from app.services.tools import ToolService

        if tool_permissions is None:
            _, tool_permissions = ToolService(self.session).list_permissions()

        settings = get_settings()
        config_by_key = self._load_entry_configs()
        workspace_root = self._workspace_root()
        return resolve_skills(
            bundled_root=settings.bundled_skills_root,
            user_root=settings.user_skills_root,
            workspace_root=workspace_root / "skills",
            os_name=self._normalized_os_name(),
            available_tools={
                permission.tool_name
                for permission in tool_permissions
                if permission.permission_level != "deny"
            },
            available_env=dict(os.environ),
            config_by_key=config_by_key,
        )

    def _load_entry_configs(self) -> dict[str, SkillEntryConfig]:
        rows = self.repository.list_settings_by_scope_prefix("skills.entries.")
        grouped: dict[str, dict[str, str | None]] = {}
        for row in rows:
            skill_key = row.scope.removeprefix("skills.entries.")
            grouped.setdefault(skill_key, {})[row.key] = row.value_json or row.value_text

        config_by_key: dict[str, SkillEntryConfig] = {}
        for skill_key, values in grouped.items():
            enabled = None
            if values.get("enabled") is not None:
                enabled = str(values["enabled"]).lower() == "true"
            config = None
            if values.get("config"):
                parsed = json.loads(str(values["config"]))
                if isinstance(parsed, dict):
                    config = parsed
            env: dict[str, str] = {}
            env_keys = []
            if values.get("env_keys"):
                parsed = json.loads(str(values["env_keys"]))
                if isinstance(parsed, list):
                    env_keys = [item for item in parsed if isinstance(item, str)]
            for env_name in env_keys:
                secret = self.secret_store.get_skill_env_value(skill_key, env_name)
                if secret:
                    env[env_name] = secret
            config_by_key[skill_key] = SkillEntryConfig(enabled=enabled, config=config, env=env)
        return config_by_key

    def _configured_env_keys_for(self, skill_key: str) -> set[str]:
        row = self.repository.get_setting(self._entry_scope(skill_key), "env_keys")
        if row is None or not row.value_json:
            return set()
        parsed = json.loads(row.value_json)
        if not isinstance(parsed, list):
            return set()
        return {item for item in parsed if isinstance(item, str)}

    def _workspace_root(self) -> Path:
        setting = self.repository.get_setting("security", "workspace_root")
        if setting and setting.value_text:
            return Path(setting.value_text).resolve()
        return get_settings().default_workspace_root

    @staticmethod
    def _normalized_os_name() -> str:
        system = platform.system().lower()
        return {
            "darwin": "darwin",
            "windows": "windows",
            "linux": "linux",
        }.get(system, system)

    @staticmethod
    def _primary_env_for(metadata: dict[str, object]) -> str | None:
        forkclaw = metadata.get("forkclaw")
        if not isinstance(forkclaw, dict):
            return None
        primary_env = forkclaw.get("primaryEnv")
        return primary_env if isinstance(primary_env, str) and primary_env else None

    def _to_read_model(self, item, *, configured_env_keys: set[str]) -> SkillRead:
        return SkillRead(
            key=item.key,
            name=item.name,
            description=item.description,
            origin=item.origin,
            enabled=item.enabled,
            eligible=item.eligible,
            selected=item.selected,
            blocked_reasons=item.blocked_reasons,
            config=item.config,
            configured_env_keys=sorted(configured_env_keys),
            primary_env=self._primary_env_for(item.metadata),
        )

    @staticmethod
    def _entry_scope(skill_key: str) -> str:
        return f"skills.entries.{skill_key}"

    @staticmethod
    def _json_dump(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def to_kernel_skill_resolution(bundle: ExecutionSkillsBundle) -> KernelSkillResolution:
        return KernelSkillResolution(strategy=bundle.strategy, items=bundle.summaries)
