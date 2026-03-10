from __future__ import annotations

import json
from pathlib import Path

from nanobot.providers.base import ToolCallRequest
from sqlmodel import Session

from app.core.config import get_settings
from app.core.provider_catalog import ToolFormat
from app.kernel.contracts import KernelExecutionRequest
from app.models.entities import ToolPermission
from app.repositories.agent_profile import AgentProfileRepository
from app.repositories.tools import ToolingRepository
from app.schemas.tool import PermissionLevel
from app.tools.base import ToolExecutionContext, ToolExecutionOutcome, ToolExecutionPort
from app.tools.registry import build_tool_registry


class ToolService(ToolExecutionPort):
    def __init__(self, session: Session):
        self.agent_repository = AgentProfileRepository(session)
        self.repository = ToolingRepository(session)
        self.registry = build_tool_registry()

    def list_permissions(self) -> tuple[str, list[ToolPermission]]:
        agent = self.agent_repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        workspace_root = self._workspace_root()
        permissions = self.repository.list_permissions(agent.id)
        return str(workspace_root), permissions

    def update_permission(self, tool_name: str, level: PermissionLevel) -> ToolPermission:
        agent = self.agent_repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        self.registry.get(tool_name)
        permission = self.repository.get_permission(agent.id, tool_name)
        if permission is None:
            msg = f"Tool permission not found for {tool_name}."
            raise ValueError(msg)

        permission.permission_level = level
        permission.approval_required = level == "ask"
        if permission.tool_name.startswith(("list_", "read_", "write_", "edit_")):
            permission.workspace_path = str(self._workspace_root())
        else:
            permission.workspace_path = None
        saved = self.repository.save_permission(permission)
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
        return self.repository.list_tool_calls(agent.id)

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
            approval = self.repository.create_approval(
                agent_id=request.identity.agent_id,
                task_id=request.runtime.task_id,
                tool_call_id=tool_record.id,
                requested_action=f"{tool_call.name}({tool_call.arguments})",
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
        context = ToolExecutionContext(workspace_root=self._context_workspace_root(permission))
        return tool.execute(context=context, arguments=arguments)

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

    def _context_workspace_root(self, permission: ToolPermission) -> Path:
        if permission.workspace_path:
            return Path(permission.workspace_path).resolve()
        return self._workspace_root()
