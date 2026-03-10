from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.entities import Approval, Message, SessionRecord, Task, TaskRun, ToolCall, utc_now


@dataclass(frozen=True)
class ApprovalBundle:
    approval: Approval
    tool_call: ToolCall | None
    task: Task | None
    task_run: TaskRun | None
    session: SessionRecord | None


class ApprovalRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_approvals(self, agent_id: str) -> list[Approval]:
        statement = (
            select(Approval)
            .where(Approval.agent_id == agent_id)
            .order_by(Approval.status.asc(), Approval.created_at.desc())
        )
        return list(self.session.exec(statement))

    def get_approval(self, approval_id: str) -> Approval | None:
        statement = select(Approval).where(Approval.id == approval_id)
        return self.session.exec(statement).first()

    def get_tool_call(self, tool_call_id: str | None) -> ToolCall | None:
        if tool_call_id is None:
            return None
        statement = select(ToolCall).where(ToolCall.id == tool_call_id)
        return self.session.exec(statement).first()

    def get_task(self, task_id: str | None) -> Task | None:
        if task_id is None:
            return None
        statement = select(Task).where(Task.id == task_id)
        return self.session.exec(statement).first()

    def get_task_run_by_id(self, task_run_id: str | None) -> TaskRun | None:
        if task_run_id is None:
            return None
        statement = select(TaskRun).where(TaskRun.id == task_run_id)
        return self.session.exec(statement).first()

    def get_task_run_for_tool_call(self, tool_call: ToolCall | None) -> TaskRun | None:
        if tool_call is None or tool_call.task_run_id is None:
            return None
        return self.get_task_run_by_id(tool_call.task_run_id)

    def get_session(self, session_id: str | None) -> SessionRecord | None:
        if session_id is None:
            return None
        statement = select(SessionRecord).where(SessionRecord.id == session_id)
        return self.session.exec(statement).first()

    def get_message(self, message_id: str | None) -> Message | None:
        if message_id is None:
            return None
        statement = select(Message).where(Message.id == message_id)
        return self.session.exec(statement).first()

    def get_bundle(self, approval_id: str) -> ApprovalBundle | None:
        approval = self.get_approval(approval_id)
        if approval is None:
            return None
        tool_call = self.get_tool_call(approval.tool_call_id)
        task = self.get_task(approval.task_id)
        task_run = self.get_task_run_for_tool_call(tool_call)
        session = self.get_session(tool_call.session_id if tool_call else None)
        return ApprovalBundle(
            approval=approval,
            tool_call=tool_call,
            task=task,
            task_run=task_run,
            session=session,
        )

    def update_approval(self, approval: Approval, *, status: str) -> Approval:
        approval.status = status
        approval.decided_at = utc_now()
        approval.updated_at = utc_now()
        self.session.add(approval)
        self.session.commit()
        self.session.refresh(approval)
        return approval
