from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session

from app.models.entities import Approval, AuditEvent, Task, TaskRun, ToolCall
from app.repositories.activity import ActivityRepository
from app.schemas.activity import (
    ActivityAuditEventRead,
    ActivityTimelineEntryRead,
    ActivityTimelineItemRead,
    ActivityTimelineResponse,
)
from app.schemas.skill import SkillSummaryRead


class ActivityService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ActivityRepository(session)

    def get_timeline(self, limit: int = 20) -> ActivityTimelineResponse:
        agent = self.repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        items = []
        for task_run, task, session_record, cron_job in self.repository.list_recent_task_runs(
            agent.id,
            limit=limit,
        ):
            items.append(self._build_item(task_run, task, session_record, cron_job))
        return ActivityTimelineResponse(items=items)

    def _build_item(
        self,
        task_run: TaskRun,
        task: Task,
        session_record,
        cron_job,
    ) -> ActivityTimelineItemRead:
        payload = self._parse_json(task.payload_json)
        user_message = self.repository.get_message(str(payload.get("user_message_id")))
        if user_message is None:
            user_message = self.repository.find_user_message_for_task(task)

        assistant_messages = self.repository.list_assistant_messages_after_task(task)
        tool_calls = self.repository.list_tool_calls(task_run.id)
        approvals = self.repository.list_approvals(
            task.id,
            [item.id for item in tool_calls],
        )
        audit_events = self.repository.list_audit_events(
            task_run_id=task_run.id,
            task_id=task.id,
            tool_call_ids=[item.id for item in tool_calls],
            approval_ids=[item.id for item in approvals],
        )

        entries: list[ActivityTimelineEntryRead] = []

        if user_message is not None:
            entries.append(
                ActivityTimelineEntryRead(
                    id=f"message:{user_message.id}",
                    type="message",
                    created_at=user_message.created_at,
                    status=user_message.status,
                    title="User message",
                    summary=user_message.content_text,
                    metadata={"message_id": user_message.id, "role": user_message.role},
                )
            )

        entries.append(
            ActivityTimelineEntryRead(
                id=f"task:{task.id}",
                type="task",
                created_at=task.created_at,
                status=task.status,
                title=task.title,
                summary=self._task_summary(task, cron_job.name if cron_job else None),
                metadata={
                    "task_id": task.id,
                    "task_kind": task.kind,
                    "session_id": task.session_id,
                    "cron_job_id": task.cron_job_id,
                },
            )
        )

        for tool_call in tool_calls:
            entries.append(self._tool_call_entry(tool_call))

        for approval in approvals:
            entries.append(self._approval_entry(approval))

        for message in assistant_messages:
            entries.append(
                ActivityTimelineEntryRead(
                    id=f"assistant:{message.id}",
                    type="message",
                    created_at=message.created_at,
                    status=message.status,
                    title="Assistant message",
                    summary=message.content_text,
                    metadata={"message_id": message.id, "role": message.role},
                )
            )

        entries.append(
            ActivityTimelineEntryRead(
                id=f"status:{task_run.id}",
                type="status",
                created_at=task_run.finished_at or task_run.updated_at,
                status=task_run.status,
                title="Execution status",
                summary=self._status_summary(task_run),
                error_message=task_run.error_message,
                duration_ms=task_run.duration_ms,
                estimated_cost_usd=task_run.estimated_cost_usd,
                metadata={"task_run_id": task_run.id},
            )
        )

        entries.extend(self._audit_entries(audit_events))
        entries.sort(key=self._entry_sort_key)
        skill_strategy, resolved_skills = self._skill_resolution(task_run.output_json)

        session_title = (
            session_record.title
            if session_record is not None
            else cron_job.name if cron_job else None
        )

        return ActivityTimelineItemRead(
            task_run_id=task_run.id,
            task_id=task.id,
            task_kind=task.kind,
            task_title=task.title,
            session_id=session_record.id if session_record is not None else None,
            session_title=session_title,
            started_at=task_run.started_at,
            finished_at=task_run.finished_at,
            status=task_run.status,
            error_message=task_run.error_message,
            duration_ms=task_run.duration_ms,
            estimated_cost_usd=task_run.estimated_cost_usd,
            skill_strategy=skill_strategy,
            resolved_skills=resolved_skills,
            entries=entries,
            audit_log=[
                ActivityAuditEventRead(
                    id=event.id,
                    level=event.level,
                    event_type=event.event_type,
                    entity_type=event.entity_type,
                    entity_id=event.entity_id,
                    summary_text=event.summary_text,
                    payload_json=event.payload_json,
                    created_at=event.created_at,
                )
                for event in audit_events
            ],
        )

    @staticmethod
    def _parse_json(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _task_summary(task: Task, cron_job_name: str | None) -> str:
        if task.kind == "agent_execution":
            return "Execution created from a user-triggered agent request."
        if task.kind == "cron_job":
            return f"Scheduled job queued: {cron_job_name or task.title}."
        if task.kind == "heartbeat":
            return "Heartbeat reviewed pending work and internal health."
        return task.kind

    @staticmethod
    def _tool_call_entry(tool_call: ToolCall) -> ActivityTimelineEntryRead:
        payload = ActivityService._parse_json(tool_call.output_json)
        summary = (
            payload.get("text")
            or payload.get("message")
            or payload.get("error")
            or tool_call.tool_name
        )
        return ActivityTimelineEntryRead(
            id=f"tool:{tool_call.id}",
            type="tool_call",
            created_at=tool_call.created_at,
            status=tool_call.status,
            title=f"Tool call: {tool_call.tool_name}",
            summary=str(summary),
            error_message=str(payload.get("error")) if payload.get("error") else None,
            metadata={
                "tool_name": tool_call.tool_name,
                "input_json": tool_call.input_json,
                "output_json": tool_call.output_json,
            },
        )

    @staticmethod
    def _approval_entry(approval: Approval) -> ActivityTimelineEntryRead:
        return ActivityTimelineEntryRead(
            id=f"approval:{approval.id}",
            type="approval",
            created_at=approval.created_at,
            status=approval.status,
            title="Approval request",
            summary=approval.requested_action,
            metadata={
                "approval_id": approval.id,
                "reason": approval.reason,
                "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
            },
        )

    @staticmethod
    def _audit_entries(audit_events: list[AuditEvent]) -> list[ActivityTimelineEntryRead]:
        items = []
        for event in audit_events:
            if event.level == "info":
                continue
            items.append(
                ActivityTimelineEntryRead(
                    id=f"audit:{event.id}",
                    type="audit",
                    created_at=event.created_at,
                    status=event.level,
                    title=event.event_type,
                    summary=event.summary_text or event.event_type,
                    metadata={
                        "entity_type": event.entity_type,
                        "entity_id": event.entity_id,
                        "payload_json": event.payload_json,
                    },
                )
            )
        return items

    @staticmethod
    def _status_summary(task_run: TaskRun) -> str:
        if task_run.status == "completed":
            return "Execution completed."
        if task_run.status == "awaiting_approval":
            return "Execution paused awaiting approval."
        if task_run.status == "failed":
            return "Execution failed."
        return f"Execution status: {task_run.status}."

    @staticmethod
    def _skill_resolution(output_json: str | None) -> tuple[str | None, list[SkillSummaryRead]]:
        if not output_json:
            return None, []
        try:
            payload = json.loads(output_json)
        except json.JSONDecodeError:
            return None, []
        skills = payload.get("skills")
        if not isinstance(skills, dict):
            return None, []
        strategy = skills.get("strategy")
        items = skills.get("items")
        if not isinstance(items, list):
            return strategy if isinstance(strategy, str) else None, []
        summaries: list[SkillSummaryRead] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("selected"):
                continue
            try:
                summaries.append(SkillSummaryRead.model_validate(item))
            except Exception:
                continue
        return strategy if isinstance(strategy, str) else None, summaries

    @staticmethod
    def _entry_sort_key(item: ActivityTimelineEntryRead) -> tuple[object, int, str]:
        type_priority = {
            "message": 0,
            "task": 1,
            "tool_call": 2,
            "approval": 3,
            "status": 4,
            "audit": 5,
        }
        return (item.created_at, type_priority.get(item.type, 99), item.id)
