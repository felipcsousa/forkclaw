from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.models.entities import Approval, AuditEvent, Message, Task, TaskRun, ToolCall
from app.repositories.activity import ActivityRepository
from app.schemas.activity import (
    ActivityAuditEventRead,
    ActivitySubagentLineageRead,
    ActivityTimelineEntryRead,
    ActivityTimelineItemRead,
    ActivityTimelineResponse,
)
from app.schemas.skill import SkillSummaryRead

LEGACY_SUBAGENT_EVENT_TYPE_MAP = {
    "subagent.run.started": "subagent.started",
    "subagent.run.completed": "subagent.completed",
    "subagent.run.failed": "subagent.failed",
    "subagent.run.cancelled": "subagent.cancelled",
    "subagent.run.timed_out": "subagent.timed_out",
}

PUBLIC_SUBAGENT_EVENT_TYPES = {
    "subagent.spawned",
    "subagent.started",
    "subagent.completed",
    "subagent.failed",
    "subagent.cancel_requested",
    "subagent.cancelled",
    "subagent.timed_out",
}

PUBLIC_TOOL_EVENT_TYPES = {
    "tool.started",
    "tool.completed",
    "tool.failed",
}


@dataclass
class ActivityPreloadContext:
    user_messages_by_id: dict[str, Message]
    assistant_messages_by_session: dict[str, list[Message]]
    tool_calls_by_task_run: dict[str, list[ToolCall]]
    approvals_by_task: dict[str, list[Approval]]
    approvals_by_tool_call: dict[str, list[Approval]]
    audit_events_by_entity: dict[str, list[AuditEvent]]
    lineage_by_task_run: dict[str, tuple[object, object, object | None]]


class ActivityService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ActivityRepository(session)

    def get_timeline(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ActivityTimelineResponse:
        agent = self.repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        rows = self.repository.list_recent_task_runs_page(
            agent.id,
            limit=limit + 1,
            cursor=self._decode_cursor(cursor),
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        context = self._preload_context(page_rows)
        items = [
            self._build_item(task_run, task, session_record, cron_job, context)
            for task_run, task, session_record, cron_job in page_rows
        ]
        next_cursor = (
            self._encode_cursor(page_rows[-1][0].created_at, page_rows[-1][0].id)
            if has_more and page_rows
            else None
        )
        return ActivityTimelineResponse(items=items, next_cursor=next_cursor)

    def _preload_context(
        self,
        rows: list[tuple[TaskRun, Task, object | None, object | None]],
    ) -> ActivityPreloadContext:
        if not rows:
            return ActivityPreloadContext(
                user_messages_by_id={},
                assistant_messages_by_session={},
                tool_calls_by_task_run={},
                approvals_by_task={},
                approvals_by_tool_call={},
                audit_events_by_entity={},
                lineage_by_task_run={},
            )

        payloads_by_task_id = {
            task.id: self._parse_json(task.payload_json)
            for _task_run, task, _session, _cron in rows
        }
        user_message_ids = [
            user_message_id
            for payload in payloads_by_task_id.values()
            for user_message_id in [payload.get("user_message_id")]
            if isinstance(user_message_id, str)
        ]
        user_messages_by_id = self.repository.list_messages_by_ids(user_message_ids)

        session_ids = [
            session_record.id
            for _task_run, _task, session_record, _cron in rows
            if session_record is not None
        ]
        min_task_created_at = min(task.created_at for _task_run, task, _session, _cron in rows)
        assistant_messages_by_session = self.repository.list_assistant_messages_for_sessions(
            session_ids,
            created_after=min_task_created_at,
        )

        task_run_ids = [task_run.id for task_run, _task, _session, _cron in rows]
        tool_calls_by_task_run = self.repository.list_tool_calls_by_task_run_ids(task_run_ids)
        task_ids = [task.id for _task_run, task, _session, _cron in rows]
        tool_call_ids = [
            tool_call.id
            for tool_calls in tool_calls_by_task_run.values()
            for tool_call in tool_calls
        ]
        approvals_by_task, approvals_by_tool_call = (
            self.repository.list_approvals_for_tasks_or_tool_calls(task_ids, tool_call_ids)
        )
        has_subagent_runs = any(
            task.kind == "subagent_execution"
            for _task_run, task, _session, _cron in rows
        )
        lineage_by_task_run = (
            self.repository.list_subagent_lineage_by_task_run_ids(task_run_ids)
            if has_subagent_runs
            else {}
        )

        approval_ids = [
            approval.id
            for approvals in approvals_by_task.values()
            for approval in approvals
        ]
        extra_entity_ids = []
        for lineage in lineage_by_task_run.values():
            subagent_run, child_session, _parent_session = lineage
            extra_entity_ids.extend([subagent_run.id, child_session.id])
        entity_ids = [*task_run_ids, *task_ids, *tool_call_ids, *approval_ids, *extra_entity_ids]
        audit_events_by_entity = self.repository.list_audit_events_by_entity_ids(entity_ids)

        return ActivityPreloadContext(
            user_messages_by_id=user_messages_by_id,
            assistant_messages_by_session=assistant_messages_by_session,
            tool_calls_by_task_run=tool_calls_by_task_run,
            approvals_by_task=approvals_by_task,
            approvals_by_tool_call=approvals_by_tool_call,
            audit_events_by_entity=audit_events_by_entity,
            lineage_by_task_run=lineage_by_task_run,
        )

    def _build_item(
        self,
        task_run: TaskRun,
        task: Task,
        session_record,
        cron_job,
        context: ActivityPreloadContext,
    ) -> ActivityTimelineItemRead:
        payload = self._parse_json(task.payload_json)
        user_message = None
        user_message_id = payload.get("user_message_id")
        if isinstance(user_message_id, str):
            user_message = context.user_messages_by_id.get(user_message_id)
        if user_message is None:
            user_message = self.repository.find_user_message_for_task(task)

        assistant_messages = self._assistant_messages_for_task(
            task,
            context.assistant_messages_by_session,
        )
        tool_calls = context.tool_calls_by_task_run.get(task_run.id, [])
        approvals = self._approvals_for_item(task.id, tool_calls, context)
        subagent_lineage = context.lineage_by_task_run.get(task_run.id)
        audit_events = self._audit_events_for_item(
            task_run_id=task_run.id,
            task_id=task.id,
            tool_calls=tool_calls,
            approvals=approvals,
            subagent_lineage=subagent_lineage,
            context=context,
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

        entries.extend(self._tool_call_entry(tool_call) for tool_call in tool_calls)
        entries.extend(self._approval_entry(approval) for approval in approvals)
        entries.extend(
            ActivityTimelineEntryRead(
                id=f"assistant:{message.id}",
                type="message",
                created_at=message.created_at,
                status=message.status,
                title="Assistant message",
                summary=message.content_text,
                metadata={"message_id": message.id, "role": message.role},
            )
            for message in assistant_messages
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
            lineage=self._build_lineage(subagent_lineage, task_run),
            entries=entries,
            audit_log=[
                ActivityAuditEventRead(
                    id=event.id,
                    level=event.level,
                    event_type=self._normalize_subagent_event_type(event.event_type),
                    entity_type=event.entity_type,
                    entity_id=event.entity_id,
                    summary_text=event.summary_text,
                    payload_json=None,
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
    def _encode_cursor(created_at: datetime, task_run_id: str) -> str:
        payload = json.dumps(
            {"created_at": created_at.isoformat(), "task_run_id": task_run_id},
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> tuple[datetime, str] | None:
        if not cursor:
            return None
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
            payload = json.loads(decoded)
            created_at = datetime.fromisoformat(payload["created_at"])
            task_run_id = str(payload["task_run_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            msg = "Invalid activity cursor."
            raise ValueError(msg) from None
        return created_at, task_run_id

    @staticmethod
    def _assistant_messages_for_task(
        task: Task,
        assistant_messages_by_session: dict[str, list[Message]],
    ) -> list[Message]:
        if task.session_id is None:
            return []
        return [
            message
            for message in assistant_messages_by_session.get(task.session_id, [])
            if message.created_at >= task.created_at
        ][:3]

    @staticmethod
    def _approvals_for_item(
        task_id: str,
        tool_calls: list[ToolCall],
        context: ActivityPreloadContext,
    ) -> list[Approval]:
        items: dict[str, Approval] = {
            approval.id: approval
            for approval in context.approvals_by_task.get(task_id, [])
        }
        for tool_call in tool_calls:
            for approval in context.approvals_by_tool_call.get(tool_call.id, []):
                items.setdefault(approval.id, approval)
        return sorted(items.values(), key=lambda item: item.created_at)

    @staticmethod
    def _audit_events_for_item(
        *,
        task_run_id: str,
        task_id: str,
        tool_calls: list[ToolCall],
        approvals: list[Approval],
        subagent_lineage,
        context: ActivityPreloadContext,
    ) -> list[AuditEvent]:
        entity_ids = [
            task_run_id,
            task_id,
            *[item.id for item in tool_calls],
            *[item.id for item in approvals],
        ]
        if subagent_lineage is not None:
            subagent_run, child_session, _parent_session = subagent_lineage
            entity_ids.extend([subagent_run.id, child_session.id])
        events: dict[str, AuditEvent] = {}
        for entity_id in entity_ids:
            for event in context.audit_events_by_entity.get(entity_id, []):
                events.setdefault(event.id, event)
        return sorted(events.values(), key=lambda item: item.created_at)

    @staticmethod
    def _task_summary(task: Task, cron_job_name: str | None) -> str:
        if task.kind == "agent_execution":
            return "Execution created from a user-triggered agent request."
        if task.kind == "cron_job":
            return f"Scheduled job queued: {cron_job_name or task.title}."
        if task.kind == "heartbeat":
            return "Heartbeat reviewed pending work and internal health."
        if task.kind == "subagent_execution":
            return "Delegated child session execution."
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
            metadata={"tool_name": tool_call.tool_name},
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
            normalized_type = ActivityService._normalize_subagent_event_type(event.event_type)
            is_public_subagent_event = normalized_type in PUBLIC_SUBAGENT_EVENT_TYPES
            is_public_tool_event = normalized_type in PUBLIC_TOOL_EVENT_TYPES
            if event.level == "info" and not is_public_subagent_event and not is_public_tool_event:
                continue
            payload = ActivityService._parse_json(event.payload_json)
            items.append(
                ActivityTimelineEntryRead(
                    id=f"audit:{event.id}",
                    type="audit",
                    created_at=event.created_at,
                    status=event.level,
                    title=normalized_type,
                    summary=ActivityService._audit_summary(
                        event_type=normalized_type,
                        payload=payload,
                        fallback_summary=event.summary_text,
                    ),
                    metadata={
                        "entity_type": event.entity_type,
                        "entity_id": event.entity_id,
                        "status": payload.get("status")
                        if isinstance(payload.get("status"), str)
                        else None,
                        "task_run_id": payload.get("task_run_id")
                        if isinstance(payload.get("task_run_id"), str)
                        else None,
                    },
                )
            )
        return items

    @staticmethod
    def _build_lineage(
        subagent_lineage,
        task_run: TaskRun,
    ) -> ActivitySubagentLineageRead | None:
        if subagent_lineage is None:
            return None

        _subagent_run, child_session, parent_session = subagent_lineage
        goal_summary = " ".join((child_session.delegated_goal or child_session.title).split())[:160]
        return ActivitySubagentLineageRead(
            parent_session_id=child_session.parent_session_id or "",
            parent_session_title=parent_session.title if parent_session is not None else None,
            child_session_id=child_session.id,
            child_session_title=child_session.title,
            goal_summary=goal_summary,
            status=task_run.status,
            task_run_id=task_run.id,
            estimated_cost_usd=task_run.estimated_cost_usd,
        )

    @staticmethod
    def _audit_summary(
        *,
        event_type: str,
        payload: dict[str, Any],
        fallback_summary: str | None,
    ) -> str:
        explicit_summary = payload.get("summary")
        if isinstance(explicit_summary, str) and explicit_summary.strip():
            return explicit_summary.strip()

        goal_summary = payload.get("goal_summary")
        if event_type in PUBLIC_SUBAGENT_EVENT_TYPES and isinstance(goal_summary, str):
            return goal_summary
        if event_type in PUBLIC_TOOL_EVENT_TYPES and isinstance(fallback_summary, str):
            return fallback_summary.strip()

        if isinstance(fallback_summary, str) and fallback_summary.strip():
            return fallback_summary.strip()
        return event_type

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
    def _normalize_subagent_event_type(event_type: str) -> str:
        return LEGACY_SUBAGENT_EVENT_TYPE_MAP.get(event_type, event_type)

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
