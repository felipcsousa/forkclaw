from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nanobot.providers.base import ToolCallRequest
from sqlmodel import Session

from app.core.config import get_settings
from app.core.provider_catalog import ToolFormat
from app.kernel.contracts import KernelExecutionRequest
from app.models.entities import ToolPermission, ToolPolicyOverride
from app.repositories.agent_profile import AgentProfileRepository
from app.repositories.tools import ToolingRepository
from app.schemas.skill import SkillSummaryRead
from app.schemas.tool import PermissionLevel, ToolCallRead
from app.tools.base import ToolExecutionContext, ToolExecutionOutcome, ToolExecutionPort
from app.tools.catalog import ToolCatalogEntry, build_tool_catalog
from app.tools.policies import (
    ToolPolicyProfile,
    ToolPolicyProfileId,
    get_tool_policy_profile,
    list_tool_policy_profiles,
    resolve_effective_permission_level,
)
from app.tools.registry import build_tool_registry
from app.tools.web.cache import SqlToolCacheStore


class ToolService(ToolExecutionPort):
    def __init__(self, session: Session):
        self.agent_repository = AgentProfileRepository(session)
        self.repository = ToolingRepository(session)
        self.registry = build_tool_registry()
        self.catalog = build_tool_catalog()
        self.catalog_tool_names = {item.id for item in self.catalog}

    def list_permissions(self) -> tuple[str, list[ToolPermission]]:
        agent = self.agent_repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        self._materialize_permissions(agent.id)
        workspace_root = self._workspace_root()
        permissions = [
            permission
            for permission in self.repository.list_permissions(agent.id)
            if permission.tool_name in self.catalog_tool_names
        ]
        return str(workspace_root), permissions

    def list_catalog(self) -> list[ToolCatalogEntry]:
        return self.catalog

    def get_policy(
        self,
    ) -> tuple[
        ToolPolicyProfileId,
        list[ToolPolicyProfile],
        list[ToolPolicyOverride],
    ]:
        agent = self._require_default_agent()
        self._materialize_permissions(agent.id)
        profile_id = self._active_profile_id()
        profiles = list_tool_policy_profiles()
        overrides = [
            override
            for override in self.repository.list_overrides(agent.id)
            if override.tool_name in self.catalog_tool_names
        ]
        return profile_id, profiles, overrides

    def update_policy_profile(
        self,
        profile_id: ToolPolicyProfileId,
    ) -> tuple[ToolPolicyProfileId, list[ToolPolicyProfile], list[ToolPolicyOverride]]:
        agent = self._require_default_agent()
        get_tool_policy_profile(profile_id)
        self.repository.upsert_setting(
            scope="tools",
            key="policy_profile",
            value_type="string",
            value_text=profile_id,
        )
        self._materialize_permissions(agent.id)
        return self.get_policy()

    def update_permission(self, tool_name: str, level: PermissionLevel) -> ToolPermission:
        agent = self._require_default_agent()
        catalog_entry = self._require_catalog_entry(tool_name)
        self._materialize_permissions(agent.id)

        default_level = resolve_effective_permission_level(
            profile_id=self._active_profile_id(),
            tool_group=catalog_entry.group,
            override_level=None,
        )
        override = self.repository.get_override(agent.id, tool_name)

        if level == default_level:
            if override is not None:
                self.repository.delete_override(override)
        else:
            if override is None:
                override = ToolPolicyOverride(
                    agent_id=agent.id,
                    tool_name=tool_name,
                    permission_level=level,
                    status="active",
                )
            else:
                override.permission_level = level
                override.status = "active"
            self.repository.save_override(override)

        self._materialize_permissions(agent.id)
        saved = self.repository.get_permission(agent.id, tool_name)
        if saved is None:
            msg = f"Tool permission not found for {tool_name}."
            raise ValueError(msg)
        self.repository.record_audit_event(
            agent_id=agent.id,
            event_type="tool_permission.updated",
            entity_type="tool_permission",
            entity_id=saved.id,
            payload={"tool_name": tool_name, "permission_level": level},
        )
        return saved

    def list_tool_calls(self) -> list:
        agent = self.agent_repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)
        self._materialize_permissions(agent.id)
        calls = self.repository.list_tool_calls(agent.id)
        outputs = self.repository.get_task_run_outputs(
            [call.task_run_id for call in calls if call.task_run_id]
        )
        return [
            ToolCallRead(
                id=call.id,
                session_id=call.session_id,
                message_id=call.message_id,
                task_run_id=call.task_run_id,
                tool_name=call.tool_name,
                status=call.status,
                input_json=call.input_json,
                output_json=call.output_json,
                started_at=call.started_at,
                finished_at=call.finished_at,
                created_at=call.created_at,
                updated_at=call.updated_at,
                guided_by_skills=self._skill_summaries_from_output(
                    outputs.get(call.task_run_id or "")
                ),
            )
            for call in calls
        ]

    def describe_tools(
        self,
        tool_names: list[str] | None = None,
        *,
        format: ToolFormat = "openai",
    ) -> list[dict]:
        return self.registry.describe(tool_names, format=format)

    def execute_tool_call(
        self,
        *,
        request: KernelExecutionRequest,
        tool_call: ToolCallRequest,
        approval_override: bool = False,
    ) -> ToolExecutionOutcome:
        allowed_tool_names = {tool.tool_name for tool in request.tools}
        if tool_call.name not in allowed_tool_names:
            tool_record = self.repository.create_tool_call(
                session_id=request.session.session_id,
                message_id=request.runtime.trigger_message_id,
                task_run_id=request.runtime.task_run_id,
                tool_name=tool_call.name,
                input_payload=tool_call.arguments,
            )
            self.repository.update_tool_call(
                tool_record,
                status="denied",
                output_payload={"message": "Tool is outside the delegated scope."},
            )
            self.repository.record_audit_event(
                agent_id=request.identity.agent_id,
                event_type="tool_call.denied",
                entity_type="tool_call",
                entity_id=tool_record.id,
                payload={"tool_name": tool_call.name, "reason": "outside_scope"},
            )
            return ToolExecutionOutcome(
                tool_call_id=tool_record.id,
                tool_name=tool_call.name,
                status="denied",
                output_text=f"Tool `{tool_call.name}` is outside the delegated scope.",
            )

        self._materialize_permissions(request.identity.agent_id)
        permission = self.repository.get_permission(request.identity.agent_id, tool_call.name)
        tool_record = self.repository.create_tool_call(
            session_id=request.session.session_id,
            message_id=request.runtime.trigger_message_id,
            task_run_id=request.runtime.task_run_id,
            tool_name=tool_call.name,
            input_payload=tool_call.arguments,
        )
        self.repository.record_audit_event(
            agent_id=request.identity.agent_id,
            event_type="tool_call.requested",
            entity_type="tool_call",
            entity_id=tool_record.id,
            payload={"tool_name": tool_call.name},
        )

        if permission is None or (permission.permission_level == "deny" and not approval_override):
            self.repository.update_tool_call(
                tool_record,
                status="denied",
                output_payload={"message": "Tool denied by policy."},
            )
            self.repository.record_audit_event(
                agent_id=request.identity.agent_id,
                event_type="tool_call.denied",
                entity_type="tool_call",
                entity_id=tool_record.id,
                payload={"tool_name": tool_call.name},
            )
            return ToolExecutionOutcome(
                tool_call_id=tool_record.id,
                tool_name=tool_call.name,
                status="denied",
                output_text=f"Tool `{tool_call.name}` is denied by policy.",
            )

        if permission.permission_level == "ask" and not approval_override:
            try:
                requested_action = self._requested_action(
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                )
            except Exception as exc:
                return self._record_failed_tool_call(
                    agent_id=request.identity.agent_id,
                    tool_record=tool_record,
                    tool_name=tool_call.name,
                    error=exc,
                )
            approval = self.repository.create_approval(
                agent_id=request.identity.agent_id,
                task_id=request.runtime.task_id,
                tool_call_id=tool_record.id,
                requested_action=requested_action,
                reason="Tool permission is configured as ask.",
            )
            self.repository.update_tool_call(
                tool_record,
                status="awaiting_approval",
                output_payload={"approval_id": approval.id},
            )
            self.repository.record_audit_event(
                agent_id=request.identity.agent_id,
                event_type="tool_call.approval_requested",
                entity_type="approval",
                entity_id=approval.id,
                payload={"tool_name": tool_call.name, "tool_call_id": tool_record.id},
            )
            return ToolExecutionOutcome(
                tool_call_id=tool_record.id,
                tool_name=tool_call.name,
                status="awaiting_approval",
                output_text=(
                    f"Tool `{tool_call.name}` requires approval and was not executed. "
                    f"Approval ID: {approval.id}."
                ),
                approval_id=approval.id,
            )

        return self._execute_and_record_tool_call(
            agent_id=request.identity.agent_id,
            permission=permission,
            tool_record=tool_record,
            tool_name=tool_call.name,
            arguments=tool_call.arguments,
        )

    def continue_approved_tool_call(
        self,
        *,
        request: KernelExecutionRequest,
        tool_call_id: str,
    ) -> ToolExecutionOutcome:
        tool_record = self.repository.get_tool_call(tool_call_id)
        if tool_record is None:
            msg = "Tool call not found."
            raise ValueError(msg)

        permission = self.repository.get_permission(
            request.identity.agent_id,
            tool_record.tool_name,
        )
        arguments = json.loads(tool_record.input_json or "{}")

        if permission is None:
            msg = "Tool permission not found."
            raise ValueError(msg)

        return self._execute_and_record_tool_call(
            agent_id=request.identity.agent_id,
            permission=permission,
            tool_record=tool_record,
            tool_name=tool_record.tool_name,
            arguments=arguments,
            completion_payload={"resumed": True},
        )

    def _execute_and_record_tool_call(
        self,
        *,
        agent_id: str,
        permission: ToolPermission,
        tool_record,
        tool_name: str,
        arguments: dict,
        completion_payload: dict[str, object] | None = None,
    ) -> ToolExecutionOutcome:
        try:
            self._record_tool_started(
                agent_id=agent_id,
                tool_record=tool_record,
                tool_name=tool_name,
                arguments=arguments,
            )
        except Exception as exc:
            return self._record_failed_tool_call(
                agent_id=agent_id,
                tool_record=tool_record,
                tool_name=tool_name,
                error=exc,
            )

        try:
            result = self._execute_tool(tool_name, permission, arguments)
        except Exception as exc:
            return self._record_failed_tool_call(
                agent_id=agent_id,
                tool_record=tool_record,
                tool_name=tool_name,
                error=exc,
            )

        return self._record_completed_tool_call(
            agent_id=agent_id,
            tool_record=tool_record,
            tool_name=tool_name,
            output_text=result.output_text,
            output_data=result.output_data,
            audit_payload=completion_payload,
        )

    def _execute_tool(
        self,
        tool_name: str,
        permission: ToolPermission,
        arguments: dict,
    ):
        tool = self.registry.get(tool_name)
        context = ToolExecutionContext(
            workspace_root=self._context_workspace_root(permission),
            cache_store=SqlToolCacheStore(self.repository),
            runtime_settings={
                "tool_timeout_seconds": get_settings().tool_timeout_seconds,
                "shell_exec_max_timeout_seconds": self._shell_exec_max_timeout_seconds(),
                "shell_exec_max_output_chars": self._shell_exec_max_output_chars(),
                "shell_exec_allowed_cwd_roots": self._shell_exec_allowed_cwd_roots(),
                "shell_exec_allowed_env_keys": self._shell_exec_allowed_env_keys(),
                "web_search_cache_ttl_seconds": get_settings().web_search_cache_ttl_seconds,
                "web_fetch_cache_ttl_seconds": get_settings().web_fetch_cache_ttl_seconds,
                "web_fetch_max_response_bytes": get_settings().web_fetch_max_response_bytes,
                "web_fetch_default_max_chars": get_settings().web_fetch_default_max_chars,
            },
        )
        return tool.execute(context=context, arguments=arguments)

    def _record_tool_started(
        self,
        *,
        agent_id: str,
        tool_record,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        payload = {"tool_name": tool_name}
        payload.update(self._tool_preview(tool_name=tool_name, arguments=arguments))
        summary = payload.get("summary")
        self.repository.record_audit_event(
            agent_id=agent_id,
            event_type="tool.started",
            entity_type="tool_call",
            entity_id=tool_record.id,
            payload=payload,
            summary_text=str(summary) if isinstance(summary, str) else f"Started `{tool_name}`.",
        )

    def _record_completed_tool_call(
        self,
        *,
        agent_id: str,
        tool_record,
        tool_name: str,
        output_text: str,
        output_data,
        audit_payload: dict[str, object] | None = None,
    ) -> ToolExecutionOutcome:
        self.repository.update_tool_call(
            tool_record,
            status="completed",
            output_payload={"text": output_text, "data": output_data},
        )
        payload = {"tool_name": tool_name}
        if audit_payload:
            payload.update(audit_payload)
        self.repository.record_audit_event(
            agent_id=agent_id,
            event_type="tool_call.completed",
            entity_type="tool_call",
            entity_id=tool_record.id,
            payload=payload,
        )
        completion_payload = {"tool_name": tool_name}
        if isinstance(output_data, dict):
            for key in ("exit_code", "duration_ms", "cwd_resolved", "truncated"):
                if key in output_data:
                    completion_payload[key] = output_data[key]
        self.repository.record_audit_event(
            agent_id=agent_id,
            event_type="tool.completed",
            entity_type="tool_call",
            entity_id=tool_record.id,
            payload=completion_payload,
            summary_text=f"Completed `{tool_name}`.",
        )
        return ToolExecutionOutcome(
            tool_call_id=tool_record.id,
            tool_name=tool_name,
            status="completed",
            output_text=output_text,
            output_data=output_data,
        )

    def _record_failed_tool_call(
        self,
        *,
        agent_id: str,
        tool_record,
        tool_name: str,
        error: Exception,
    ) -> ToolExecutionOutcome:
        self.repository.update_tool_call(
            tool_record,
            status="failed",
            output_payload={"error": str(error)},
        )
        self.repository.record_audit_event(
            agent_id=agent_id,
            event_type="tool_call.failed",
            entity_type="tool_call",
            entity_id=tool_record.id,
            payload={"tool_name": tool_name, "error": str(error)},
        )
        failure_payload = {"tool_name": tool_name, "error": str(error)}
        audit_payload = getattr(error, "audit_payload", None)
        if isinstance(audit_payload, dict):
            failure_payload.update(audit_payload)
        self.repository.record_audit_event(
            agent_id=agent_id,
            event_type="tool.failed",
            entity_type="tool_call",
            entity_id=tool_record.id,
            payload=failure_payload,
            level="error",
            summary_text=f"Failed `{tool_name}`: {error}",
        )
        return ToolExecutionOutcome(
            tool_call_id=tool_record.id,
            tool_name=tool_name,
            status="failed",
            output_text=f"Tool `{tool_name}` failed: {error}",
            error_message=str(error),
        )

    def _workspace_root(self) -> Path:
        setting = self.repository.get_setting("security", "workspace_root")
        if setting and setting.value_text:
            return Path(setting.value_text).resolve()
        return get_settings().default_workspace_root

    def _require_default_agent(self):
        agent = self.agent_repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)
        return agent

    def _require_catalog_entry(self, tool_name: str) -> ToolCatalogEntry:
        for item in self.catalog:
            if item.id == tool_name:
                return item
        msg = f"Unknown tool: {tool_name}"
        raise ValueError(msg)

    def _active_profile_id(self) -> ToolPolicyProfileId:
        setting = self.repository.get_setting("tools", "policy_profile")
        candidate = setting.value_text if setting and setting.value_text else "minimal"
        profile = get_tool_policy_profile(candidate)
        return profile.id

    def _materialize_permissions(self, agent_id: str) -> None:
        profile_id = self._active_profile_id()
        overrides_by_tool = {
            override.tool_name: override.permission_level
            for override in self.repository.list_overrides(agent_id)
        }
        workspace_root = str(self._workspace_root())

        for item in self.catalog:
            level = resolve_effective_permission_level(
                profile_id=profile_id,
                tool_group=item.group,
                override_level=overrides_by_tool.get(item.id),
            )
            self.repository.upsert_permission(
                agent_id=agent_id,
                tool_name=item.id,
                permission_level=level,
                workspace_path=workspace_root if item.requires_workspace else None,
                approval_required=level == "ask",
            )

    def _context_workspace_root(self, permission: ToolPermission) -> Path:
        if permission.workspace_path:
            return Path(permission.workspace_path).resolve()
        return self._workspace_root()

    def _tool_preview(self, *, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.registry.get(tool_name)
        preview_method = getattr(tool, "preview", None)
        if not callable(preview_method):
            return {}
        context = ToolExecutionContext(
            workspace_root=self._workspace_root(),
            cache_store=SqlToolCacheStore(self.repository),
            runtime_settings={
                "tool_timeout_seconds": get_settings().tool_timeout_seconds,
                "shell_exec_max_timeout_seconds": self._shell_exec_max_timeout_seconds(),
                "shell_exec_max_output_chars": self._shell_exec_max_output_chars(),
                "shell_exec_allowed_cwd_roots": self._shell_exec_allowed_cwd_roots(),
                "shell_exec_allowed_env_keys": self._shell_exec_allowed_env_keys(),
            },
        )
        preview = preview_method(context=context, arguments=arguments)
        if hasattr(preview, "__dict__"):
            payload = dict(preview.__dict__)
        elif isinstance(preview, dict):
            payload = dict(preview)
        else:
            return {}
        if tool_name == "shell_exec":
            payload["summary"] = (
                f"Running `{tool_name}` in {payload.get('cwd_resolved', self._workspace_root())}."
            )
        return payload

    def _requested_action(self, *, tool_name: str, arguments: dict[str, Any]) -> str:
        tool = self.registry.get(tool_name)
        requested_action_method = getattr(tool, "requested_action", None)
        if not callable(requested_action_method):
            return f"{tool_name}({arguments})"
        context = ToolExecutionContext(
            workspace_root=self._workspace_root(),
            cache_store=SqlToolCacheStore(self.repository),
            runtime_settings={
                "tool_timeout_seconds": get_settings().tool_timeout_seconds,
                "shell_exec_max_timeout_seconds": self._shell_exec_max_timeout_seconds(),
                "shell_exec_max_output_chars": self._shell_exec_max_output_chars(),
                "shell_exec_allowed_cwd_roots": self._shell_exec_allowed_cwd_roots(),
                "shell_exec_allowed_env_keys": self._shell_exec_allowed_env_keys(),
            },
        )
        return str(requested_action_method(context=context, arguments=arguments))

    @staticmethod
    def _skill_summaries_from_output(output_json: str | None) -> list[SkillSummaryRead]:
        if not output_json:
            return []
        try:
            payload = json.loads(output_json)
        except json.JSONDecodeError:
            return []
        skills = payload.get("skills")
        if not isinstance(skills, dict):
            return []
        items = skills.get("items")
        if not isinstance(items, list):
            return []
        summaries: list[SkillSummaryRead] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("selected"):
                continue
            try:
                summaries.append(SkillSummaryRead.model_validate(item))
            except Exception:
                continue
        return summaries

    def _shell_exec_allowed_cwd_roots(self) -> list[str]:
        setting = self.repository.get_setting("runtime", "shell_exec_allowed_cwd_roots")
        if setting and setting.value_json:
            try:
                parsed = json.loads(setting.value_json)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str)]
        return list(get_settings().shell_exec_allowed_cwd_roots)

    def _shell_exec_allowed_env_keys(self) -> list[str]:
        setting = self.repository.get_setting("runtime", "shell_exec_allowed_env_keys")
        if setting and setting.value_json:
            try:
                parsed = json.loads(setting.value_json)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str)]
        return list(get_settings().shell_exec_allowed_env_keys)

    def _shell_exec_max_output_chars(self) -> int:
        setting = self.repository.get_setting("runtime", "shell_exec_max_output_chars")
        if setting and setting.value_text:
            try:
                return int(setting.value_text)
            except ValueError:
                pass
        return get_settings().shell_exec_max_output_chars

    def _shell_exec_max_timeout_seconds(self) -> float:
        setting = self.repository.get_setting("runtime", "shell_exec_max_timeout_seconds")
        if setting and setting.value_text:
            try:
                return float(setting.value_text)
            except ValueError:
                pass
        return get_settings().shell_exec_max_timeout_seconds
