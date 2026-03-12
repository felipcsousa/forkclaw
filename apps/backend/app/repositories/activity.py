from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from app.models.entities import (
    Agent,
    Approval,
    AuditEvent,
    CronJob,
    Message,
    SessionRecord,
    SessionSubagentRun,
    Task,
    TaskRun,
    ToolCall,
)


class ActivityRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_default_agent(self) -> Agent | None:
        statement = select(Agent).where(Agent.is_default.is_(True)).order_by(Agent.created_at.asc())
        return self.session.exec(statement).first()

    def list_recent_task_runs_page(
        self,
        agent_id: str,
        *,
        limit: int,
        cursor: tuple[datetime, str] | None = None,
    ) -> list[tuple[TaskRun, Task, SessionRecord | None, CronJob | None]]:
        statement = (
            select(TaskRun, Task, SessionRecord, CronJob)
            .join(Task, Task.id == TaskRun.task_id)
            .join(SessionRecord, SessionRecord.id == Task.session_id, isouter=True)
            .join(CronJob, CronJob.id == Task.cron_job_id, isouter=True)
            .where(Task.agent_id == agent_id)
        )
        if cursor is not None:
            created_at, task_run_id = cursor
            statement = statement.where(
                or_(
                    TaskRun.created_at < created_at,
                    and_(TaskRun.created_at == created_at, TaskRun.id < task_run_id),
                )
            )
        statement = statement.order_by(TaskRun.created_at.desc(), TaskRun.id.desc()).limit(limit)
        return list(self.session.exec(statement))

    def list_messages_by_ids(self, message_ids: list[str]) -> dict[str, Message]:
        if not message_ids:
            return {}
        statement = select(Message).where(Message.id.in_(message_ids))
        return {item.id: item for item in self.session.exec(statement)}

    def find_user_message_for_task(self, task: Task) -> Message | None:
        if task.session_id is None:
            return None
        statement = (
            select(Message)
            .where(
                Message.session_id == task.session_id,
                Message.role == "user",
                Message.created_at <= task.created_at,
            )
            .order_by(Message.created_at.desc())
        )
        return self.session.exec(statement).first()

    def list_assistant_messages_for_sessions(
        self,
        session_ids: list[str],
        *,
        created_after: datetime | None,
    ) -> dict[str, list[Message]]:
        if not session_ids:
            return {}
        statement = select(Message).where(
            Message.session_id.in_(session_ids),
            Message.role == "assistant",
        )
        if created_after is not None:
            statement = statement.where(Message.created_at >= created_after)
        statement = statement.order_by(Message.session_id.asc(), Message.created_at.asc())
        grouped: dict[str, list[Message]] = defaultdict(list)
        for item in self.session.exec(statement):
            grouped[item.session_id].append(item)
        return grouped

    def list_tool_calls_by_task_run_ids(
        self,
        task_run_ids: list[str],
    ) -> dict[str, list[ToolCall]]:
        if not task_run_ids:
            return {}
        statement = (
            select(ToolCall)
            .where(ToolCall.task_run_id.in_(task_run_ids))
            .order_by(ToolCall.task_run_id.asc(), ToolCall.created_at.asc())
        )
        grouped: dict[str, list[ToolCall]] = defaultdict(list)
        for item in self.session.exec(statement):
            if item.task_run_id is not None:
                grouped[item.task_run_id].append(item)
        return grouped

    def list_approvals_for_tasks_or_tool_calls(
        self,
        task_ids: list[str],
        tool_call_ids: list[str],
    ) -> tuple[dict[str, list[Approval]], dict[str, list[Approval]]]:
        if not task_ids and not tool_call_ids:
            return {}, {}
        statement = select(Approval)
        conditions = []
        if task_ids:
            conditions.append(Approval.task_id.in_(task_ids))
        if tool_call_ids:
            conditions.append(Approval.tool_call_id.in_(tool_call_ids))
        statement = statement.where(or_(*conditions)).order_by(Approval.created_at.asc())
        by_task_id: dict[str, list[Approval]] = defaultdict(list)
        by_tool_call_id: dict[str, list[Approval]] = defaultdict(list)
        for item in self.session.exec(statement):
            if item.task_id is not None:
                by_task_id[item.task_id].append(item)
            if item.tool_call_id is not None:
                by_tool_call_id[item.tool_call_id].append(item)
        return by_task_id, by_tool_call_id

    def list_audit_events_by_entity_ids(
        self,
        entity_ids: list[str],
    ) -> dict[str, list[AuditEvent]]:
        if not entity_ids:
            return {}
        statement = (
            select(AuditEvent)
            .where(AuditEvent.entity_id.in_(entity_ids))
            .order_by(AuditEvent.created_at.asc())
        )
        grouped: dict[str, list[AuditEvent]] = defaultdict(list)
        for item in self.session.exec(statement):
            if item.entity_id is not None:
                grouped[item.entity_id].append(item)
        return grouped

    def list_subagent_lineage_by_task_run_ids(
        self,
        task_run_ids: list[str],
    ) -> dict[str, tuple[SessionSubagentRun, SessionRecord, SessionRecord | None]]:
        if not task_run_ids:
            return {}
        child_session = aliased(SessionRecord)
        parent_session = aliased(SessionRecord)
        statement = (
            select(SessionSubagentRun, child_session, parent_session)
            .join(child_session, child_session.id == SessionSubagentRun.child_session_id)
            .join(
                parent_session,
                parent_session.id == SessionSubagentRun.launcher_session_id,
                isouter=True,
            )
            .where(SessionSubagentRun.task_run_id.in_(task_run_ids))
        )
        return {
            subagent_run.task_run_id: (subagent_run, child, parent)
            for subagent_run, child, parent in self.session.exec(statement)
            if subagent_run.task_run_id is not None
        }
