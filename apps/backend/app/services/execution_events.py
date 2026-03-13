from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.models.entities import Approval, AuditEvent, Message, Task, TaskRun, ToolCall
from app.schemas.events import (
    ApprovalRequestedData,
    AssistantRunCreatedData,
    EventMessagePayload,
    ExecutionEventEnvelope,
    ExecutionStateData,
    MessageCompletedData,
    MessageUserAcceptedData,
    SubagentSpawnedData,
    ToolEventData,
)

PUBLIC_AUDIT_EVENT_TYPES = {
    "kernel.execution.started": "execution.started",
    "kernel.execution.completed": "execution.completed",
    "kernel.execution.failed": "execution.failed",
    "message.user.accepted": "message.user.accepted",
    "assistant.run.created": "assistant.run.created",
    "message.completed": "message.completed",
    "subagent.spawned": "subagent.spawned",
}

EVENT_PRIORITY = {
    "message.user.accepted": 10,
    "assistant.run.created": 20,
    "execution.started": 30,
    "tool.started": 40,
    "approval.requested": 50,
    "subagent.spawned": 60,
    "tool.completed": 70,
    "tool.failed": 80,
    "message.completed": 90,
    "execution.completed": 100,
    "execution.failed": 110,
}


class ExecutionEventService:
    def __init__(self, session: Session):
        self.session = session

    def list_events(
        self,
        *,
        session_id: str,
        task_run_id: str | None = None,
        after_event_id: str | None = None,
    ) -> list[ExecutionEventEnvelope]:
        task_runs = list(self._list_task_runs(session_id=session_id, task_run_id=task_run_id))
        task_run_ids = {item.id for item, _task in task_runs}
        task_by_run_id = {item.id: task for item, task in task_runs}
        task_run_by_id = {item.id: item for item, _task in task_runs}

        tool_calls = list(self._list_tool_calls(task_run_ids))
        tool_calls_by_id = {item.id: item for item in tool_calls}
        approvals = list(self._list_approvals(tool_calls_by_id.keys()))
        messages = list(self._list_messages(session_id))
        messages_by_id = {item.id: item for item in messages}
        audit_events = list(
            self._list_audit_events(
                session_id=session_id,
                task_run_ids=task_run_ids,
                message_ids=messages_by_id.keys(),
                include_subagent_events=task_run_id is None,
            )
        )

        events: list[ExecutionEventEnvelope] = []
        for item in audit_events:
            projected = self._project_audit_event(
                audit_event=item,
                session_id=session_id,
                task_run_id=task_run_id,
                task_by_run_id=task_by_run_id,
                task_run_by_id=task_run_by_id,
                messages_by_id=messages_by_id,
            )
            if projected is not None:
                events.append(projected)

        for tool_call in tool_calls:
            task = task_by_run_id.get(tool_call.task_run_id or "")
            if task is None:
                continue
            events.append(
                ExecutionEventEnvelope(
                    id=f"tool:{tool_call.id}:started",
                    type="tool.started",
                    created_at=tool_call.started_at or tool_call.created_at,
                    session_id=tool_call.session_id or session_id,
                    task_id=task.id,
                    task_run_id=tool_call.task_run_id,
                    data=ToolEventData(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.tool_name,
                        status="started",
                        input_json=tool_call.input_json,
                        started_at=tool_call.started_at or tool_call.created_at,
                    ),
                )
            )
            if tool_call.status == "completed" and tool_call.finished_at is not None:
                output_text = self._tool_output_text(tool_call)
                events.append(
                    ExecutionEventEnvelope(
                        id=f"tool:{tool_call.id}:completed",
                        type="tool.completed",
                        created_at=tool_call.finished_at,
                        session_id=tool_call.session_id or session_id,
                        task_id=task.id,
                        task_run_id=tool_call.task_run_id,
                        data=ToolEventData(
                            tool_call_id=tool_call.id,
                            tool_name=tool_call.tool_name,
                            status="completed",
                            input_json=tool_call.input_json,
                            output_json=tool_call.output_json,
                            started_at=tool_call.started_at,
                            finished_at=tool_call.finished_at,
                            output_text=output_text,
                        ),
                    )
                )
            if tool_call.status == "failed" and tool_call.finished_at is not None:
                events.append(
                    ExecutionEventEnvelope(
                        id=f"tool:{tool_call.id}:failed",
                        type="tool.failed",
                        created_at=tool_call.finished_at,
                        session_id=tool_call.session_id or session_id,
                        task_id=task.id,
                        task_run_id=tool_call.task_run_id,
                        data=ToolEventData(
                            tool_call_id=tool_call.id,
                            tool_name=tool_call.tool_name,
                            status="failed",
                            input_json=tool_call.input_json,
                            output_json=tool_call.output_json,
                            started_at=tool_call.started_at,
                            finished_at=tool_call.finished_at,
                            error_message=self._tool_error_message(tool_call),
                        ),
                    )
                )

        for approval in approvals:
            tool_call = tool_calls_by_id.get(approval.tool_call_id or "")
            if tool_call is None:
                continue
            task = task_by_run_id.get(tool_call.task_run_id or "")
            if task is None:
                continue
            events.append(
                ExecutionEventEnvelope(
                    id=f"approval:{approval.id}:requested",
                    type="approval.requested",
                    created_at=approval.created_at,
                    session_id=tool_call.session_id or session_id,
                    task_id=task.id,
                    task_run_id=tool_call.task_run_id,
                    data=ApprovalRequestedData(
                        approval_id=approval.id,
                        tool_call_id=approval.tool_call_id,
                        tool_name=tool_call.tool_name,
                        requested_action=approval.requested_action,
                        reason=approval.reason,
                        status=approval.status,
                    ),
                )
            )

        events.sort(
            key=lambda item: (
                item.created_at,
                EVENT_PRIORITY.get(item.type, 999),
                item.id,
            )
        )
        if after_event_id is None:
            return events

        filtered: list[ExecutionEventEnvelope] = []
        seen = False
        for item in events:
            if seen:
                filtered.append(item)
                continue
            if item.id == after_event_id:
                seen = True
        return filtered if seen else events

    def _project_audit_event(
        self,
        *,
        audit_event: AuditEvent,
        session_id: str,
        task_run_id: str | None,
        task_by_run_id: dict[str, Task],
        task_run_by_id: dict[str, TaskRun],
        messages_by_id: dict[str, Message],
    ) -> ExecutionEventEnvelope | None:
        public_type = PUBLIC_AUDIT_EVENT_TYPES.get(audit_event.event_type)
        if public_type is None:
            return None

        payload = self._parse_json(audit_event.payload_json)
        payload_session_id = payload.get("session_id")
        if public_type == "subagent.spawned":
            payload_session_id = payload.get("parent_session_id")
        if payload_session_id != session_id:
            return None

        resolved_task_run_id = payload.get("task_run_id")
        if not isinstance(resolved_task_run_id, str) and audit_event.entity_type == "task_run":
            resolved_task_run_id = audit_event.entity_id
        if task_run_id is not None and resolved_task_run_id != task_run_id:
            return None

        resolved_task_id = payload.get("task_id")
        if not isinstance(resolved_task_id, str) and isinstance(resolved_task_run_id, str):
            task = task_by_run_id.get(resolved_task_run_id)
            resolved_task_id = task.id if task is not None else None

        if public_type == "message.user.accepted":
            message_id = str(payload.get("message_id") or audit_event.entity_id or "")
            message = messages_by_id.get(message_id)
            if message is None:
                return None
            data = MessageUserAcceptedData(message=self._message_payload(message))
        elif public_type == "assistant.run.created":
            data = AssistantRunCreatedData(
                user_message_id=str(payload.get("user_message_id") or "") or None,
                status=str(payload.get("status") or "queued"),
            )
        elif public_type == "message.completed":
            message_id = str(payload.get("message_id") or audit_event.entity_id or "")
            message = messages_by_id.get(message_id)
            if message is None:
                return None
            data = MessageCompletedData(message=self._message_payload(message))
        elif public_type == "subagent.spawned":
            data = SubagentSpawnedData(
                parent_session_id=session_id,
                child_session_id=str(payload.get("child_session_id") or ""),
                status=str(payload.get("status") or "") or None,
                goal_summary=str(payload.get("goal_summary") or "") or None,
            )
        else:
            task_run = (
                task_run_by_id.get(resolved_task_run_id)
                if isinstance(resolved_task_run_id, str)
                else None
            )
            started_at = task_run.started_at if task_run is not None else None
            finished_at = task_run.finished_at if task_run is not None else None
            error_message = str(payload.get("error") or payload.get("error_message") or "") or None
            if error_message is None and task_run is not None:
                error_message = task_run.error_message
            if public_type == "execution.started" and started_at is None:
                started_at = audit_event.created_at
            if public_type == "execution.started":
                finished_at = None
            if public_type in {"execution.completed", "execution.failed"} and finished_at is None:
                finished_at = audit_event.created_at
            data = ExecutionStateData(
                status="completed" if public_type == "execution.completed" else (
                    "failed" if public_type == "execution.failed" else "running"
                ),
                error_message=error_message,
                started_at=started_at,
                finished_at=finished_at,
            )

        return ExecutionEventEnvelope(
            id=f"audit:{audit_event.id}",
            type=public_type,
            created_at=audit_event.created_at,
            session_id=session_id,
            task_id=resolved_task_id if isinstance(resolved_task_id, str) else None,
            task_run_id=resolved_task_run_id if isinstance(resolved_task_run_id, str) else None,
            data=data,
        )

    def _list_task_runs(
        self,
        *,
        session_id: str,
        task_run_id: str | None,
    ) -> Iterable[tuple[TaskRun, Task]]:
        statement = (
            select(TaskRun, Task)
            .join(Task, Task.id == TaskRun.task_id)
            .where(Task.session_id == session_id)
        )
        if task_run_id is not None:
            statement = statement.where(TaskRun.id == task_run_id)
        statement = statement.order_by(TaskRun.created_at.asc())
        return self.session.exec(statement)

    def _list_tool_calls(self, task_run_ids: set[str]) -> Iterable[ToolCall]:
        if not task_run_ids:
            return []
        statement = (
            select(ToolCall)
            .where(ToolCall.task_run_id.in_(task_run_ids))
            .order_by(ToolCall.created_at.asc())
        )
        return self.session.exec(statement)

    def _list_approvals(self, tool_call_ids: Iterable[str]) -> Iterable[Approval]:
        ids = [item for item in tool_call_ids]
        if not ids:
            return []
        statement = (
            select(Approval)
            .where(Approval.tool_call_id.in_(ids))
            .order_by(Approval.created_at.asc())
        )
        return self.session.exec(statement)

    def _list_messages(self, session_id: str) -> Iterable[Message]:
        statement = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_number.asc())
        )
        return self.session.exec(statement)

    def _list_audit_events(
        self,
        *,
        session_id: str,
        task_run_ids: set[str],
        message_ids: Iterable[str],
        include_subagent_events: bool,
    ) -> Iterable[AuditEvent]:
        message_id_list = [item for item in message_ids]
        criteria = []
        if task_run_ids:
            criteria.append(
                and_(
                    AuditEvent.entity_type == "task_run",
                    AuditEvent.entity_id.in_(task_run_ids),
                    AuditEvent.event_type.in_(
                        [
                            "kernel.execution.started",
                            "kernel.execution.completed",
                            "kernel.execution.failed",
                            "assistant.run.created",
                        ]
                    ),
                )
            )
        if message_id_list:
            criteria.append(
                and_(
                    AuditEvent.entity_type == "message",
                    AuditEvent.entity_id.in_(message_id_list),
                    AuditEvent.event_type.in_(["message.user.accepted", "message.completed"]),
                )
            )
        if include_subagent_events:
            criteria.append(
                and_(
                    AuditEvent.event_type == "subagent.spawned",
                    AuditEvent.payload_json.like(f'%"parent_session_id": "{session_id}"%'),
                )
            )

        if not criteria:
            return []

        statement = (
            select(AuditEvent)
            .where(or_(*criteria))
            .order_by(AuditEvent.created_at.asc())
        )
        return self.session.exec(statement)

    @staticmethod
    def _message_payload(message: Message) -> EventMessagePayload:
        return EventMessagePayload(
            id=message.id,
            role=message.role,
            content_text=message.content_text,
            sequence_number=message.sequence_number,
        )

    @staticmethod
    def _parse_json(value: str | None) -> dict[str, object]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _tool_output_text(tool_call: ToolCall) -> str | None:
        payload = ExecutionEventService._parse_json(tool_call.output_json)
        value = payload.get("text")
        return str(value) if isinstance(value, str) else None

    @staticmethod
    def _tool_error_message(tool_call: ToolCall) -> str | None:
        payload = ExecutionEventService._parse_json(tool_call.output_json)
        value = payload.get("error")
        return str(value) if isinstance(value, str) else None
