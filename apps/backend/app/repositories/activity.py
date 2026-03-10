from __future__ import annotations

from sqlmodel import Session, select

from app.models.entities import (
    Agent,
    Approval,
    AuditEvent,
    CronJob,
    Message,
    SessionRecord,
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

    def list_recent_task_runs(
        self,
        agent_id: str,
        limit: int = 20,
    ) -> list[tuple[TaskRun, Task, SessionRecord | None, CronJob | None]]:
        statement = (
            select(TaskRun, Task, SessionRecord, CronJob)
            .join(Task, Task.id == TaskRun.task_id)
            .join(SessionRecord, SessionRecord.id == Task.session_id, isouter=True)
            .join(CronJob, CronJob.id == Task.cron_job_id, isouter=True)
            .where(Task.agent_id == agent_id)
            .order_by(TaskRun.created_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement))

    def get_message(self, message_id: str | None) -> Message | None:
        if message_id is None:
            return None
        statement = select(Message).where(Message.id == message_id)
        return self.session.exec(statement).first()

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

    def list_assistant_messages_after_task(self, task: Task, limit: int = 3) -> list[Message]:
        if task.session_id is None:
            return []
        statement = (
            select(Message)
            .where(
                Message.session_id == task.session_id,
                Message.role == "assistant",
                Message.created_at >= task.created_at,
            )
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        return list(self.session.exec(statement))

    def list_tool_calls(self, task_run_id: str) -> list[ToolCall]:
        statement = (
            select(ToolCall)
            .where(ToolCall.task_run_id == task_run_id)
            .order_by(ToolCall.created_at.asc())
        )
        return list(self.session.exec(statement))

    def list_approvals(self, task_id: str, tool_call_ids: list[str]) -> list[Approval]:
        if tool_call_ids:
            statement = (
                select(Approval)
                .where(
                    (Approval.task_id == task_id) | (Approval.tool_call_id.in_(tool_call_ids))
                )
                .order_by(Approval.created_at.asc())
            )
        else:
            statement = (
                select(Approval)
                .where(Approval.task_id == task_id)
                .order_by(Approval.created_at.asc())
            )
        return list(self.session.exec(statement))

    def list_audit_events(
        self,
        *,
        task_run_id: str,
        task_id: str,
        tool_call_ids: list[str],
        approval_ids: list[str],
    ) -> list[AuditEvent]:
        entity_ids = [task_run_id, task_id, *tool_call_ids, *approval_ids]
        statement = (
            select(AuditEvent)
            .where(AuditEvent.entity_id.in_(entity_ids))
            .order_by(AuditEvent.created_at.asc())
        )
        return list(self.session.exec(statement))
