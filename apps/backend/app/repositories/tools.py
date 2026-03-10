from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.entities import (
    Approval,
    AuditEvent,
    Setting,
    Task,
    TaskRun,
    ToolCall,
    ToolPermission,
    utc_now,
)


class ToolingRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_permissions(self, agent_id: str) -> list[ToolPermission]:
        statement = (
            select(ToolPermission)
            .where(ToolPermission.agent_id == agent_id, ToolPermission.status == "active")
            .order_by(ToolPermission.tool_name.asc())
        )
        return list(self.session.exec(statement))

    def get_permission(self, agent_id: str, tool_name: str) -> ToolPermission | None:
        statement = (
            select(ToolPermission)
            .where(
                ToolPermission.agent_id == agent_id,
                ToolPermission.tool_name == tool_name,
                ToolPermission.status == "active",
            )
            .order_by(ToolPermission.created_at.asc())
        )
        return self.session.exec(statement).first()

    def save_permission(self, permission: ToolPermission) -> ToolPermission:
        permission.updated_at = utc_now()
        self.session.add(permission)
        self.session.commit()
        self.session.refresh(permission)
        return permission

    def list_tool_calls(self, agent_id: str, limit: int = 50) -> list[ToolCall]:
        statement = (
            select(ToolCall)
            .join(TaskRun, TaskRun.id == ToolCall.task_run_id)
            .join(Task, Task.id == TaskRun.task_id)
            .where(Task.agent_id == agent_id)
            .where(ToolCall.task_run_id.is_not(None))
            .order_by(ToolCall.created_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement))

    def get_setting(self, scope: str, key: str) -> Setting | None:
        statement = select(Setting).where(
            Setting.scope == scope,
            Setting.key == key,
            Setting.status == "active",
        )
        return self.session.exec(statement).first()

    def create_tool_call(
        self,
        *,
        session_id: str,
        message_id: str | None,
        task_run_id: str,
        tool_name: str,
        input_payload: dict[str, object],
    ) -> ToolCall:
        record = ToolCall(
            session_id=session_id,
            message_id=message_id,
            task_run_id=task_run_id,
            tool_name=tool_name,
            status="requested",
            input_json=json.dumps(input_payload, ensure_ascii=False),
            started_at=utc_now(),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def update_tool_call(
        self,
        tool_call: ToolCall,
        *,
        status: str,
        output_payload: dict[str, object] | None = None,
    ) -> ToolCall:
        tool_call.status = status
        tool_call.output_json = (
            json.dumps(output_payload, ensure_ascii=False) if output_payload is not None else None
        )
        tool_call.finished_at = utc_now()
        tool_call.updated_at = utc_now()
        self.session.add(tool_call)
        self.session.commit()
        self.session.refresh(tool_call)
        return tool_call

    def create_approval(
        self,
        *,
        agent_id: str,
        task_id: str,
        tool_call_id: str,
        requested_action: str,
        reason: str,
    ) -> Approval:
        approval = Approval(
            agent_id=agent_id,
            task_id=task_id,
            tool_call_id=tool_call_id,
            requested_action=requested_action,
            reason=reason,
            status="pending",
        )
        self.session.add(approval)
        self.session.commit()
        self.session.refresh(approval)
        return approval

    def record_audit_event(
        self,
        *,
        agent_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, object],
        level: str = "info",
        summary_text: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            agent_id=agent_id,
            actor_type="system",
            level=level,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            summary_text=summary_text,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def get_tool_call(self, tool_call_id: str) -> ToolCall | None:
        statement = select(ToolCall).where(ToolCall.id == tool_call_id)
        return self.session.exec(statement).first()

    def get_approval(self, approval_id: str) -> Approval | None:
        statement = select(Approval).where(Approval.id == approval_id)
        return self.session.exec(statement).first()

    def update_approval(self, approval: Approval, *, status: str) -> Approval:
        approval.status = status
        approval.decided_at = utc_now()
        approval.updated_at = utc_now()
        self.session.add(approval)
        self.session.commit()
        self.session.refresh(approval)
        return approval
