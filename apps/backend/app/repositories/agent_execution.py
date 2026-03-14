from __future__ import annotations

import json

from sqlmodel import Session, select, update

from app.models.entities import (
    Agent,
    AgentProfile,
    AuditEvent,
    Document,
    Message,
    SessionRecord,
    Setting,
    Task,
    TaskRun,
    ToolCall,
    ToolPermission,
    ensure_utc,
    generate_id,
    utc_now,
)


class AgentExecutionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_default_agent(self) -> Agent | None:
        statement = select(Agent).where(Agent.is_default.is_(True)).order_by(Agent.created_at.asc())
        return self.session.exec(statement).first()

    def get_agent_profile(self, agent_id: str) -> AgentProfile | None:
        statement = select(AgentProfile).where(AgentProfile.agent_id == agent_id)
        return self.session.exec(statement).first()

    def get_session(self, session_id: str) -> SessionRecord | None:
        statement = select(SessionRecord).where(SessionRecord.id == session_id)
        return self.session.exec(statement).first()

    def get_message(self, message_id: str) -> Message | None:
        statement = select(Message).where(Message.id == message_id)
        return self.session.exec(statement).first()

    def get_task(self, task_id: str) -> Task | None:
        statement = select(Task).where(Task.id == task_id)
        return self.session.exec(statement).first()

    def get_task_run(self, task_run_id: str) -> TaskRun | None:
        statement = select(TaskRun).where(TaskRun.id == task_run_id)
        return self.session.exec(statement).first()

    def get_tool_call(self, tool_call_id: str) -> ToolCall | None:
        statement = select(ToolCall).where(ToolCall.id == tool_call_id)
        return self.session.exec(statement).first()

    def create_main_session(
        self,
        *,
        agent_id: str,
        title: str | None,
    ) -> SessionRecord:
        record = SessionRecord(
            agent_id=agent_id,
            kind="main",
            title=(title or "").strip() or "Agent Session",
            status="active",
            root_session_id=None,
            spawn_depth=0,
            conversation_id=generate_id(),
            started_at=utc_now(),
        )
        record.root_session_id = record.id
        self.session.add(record)
        self.session.flush()
        return record

    def list_session_messages(
        self,
        session_id: str,
        *,
        conversation_id: str | None = None,
    ) -> list[Message]:
        statement = select(Message).where(Message.session_id == session_id)
        if conversation_id is not None:
            statement = statement.where(Message.conversation_id == conversation_id)
        statement = statement.order_by(Message.sequence_number.asc())
        return list(self.session.exec(statement))

    def list_session_messages_until(
        self,
        session_id: str,
        sequence_number: int,
        *,
        conversation_id: str | None = None,
    ) -> list[Message]:
        statement = select(Message).where(
            Message.session_id == session_id,
            Message.sequence_number <= sequence_number,
        )
        if conversation_id is not None:
            statement = statement.where(Message.conversation_id == conversation_id)
        statement = statement.order_by(Message.sequence_number.asc())
        return list(self.session.exec(statement))

    def create_message(self, session_id: str, role: str, content: str) -> Message:
        session_record = self.get_session(session_id)
        if session_record is None:
            msg = "Session not found."
            raise ValueError(msg)
        statement = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_number.desc())
        )
        latest = self.session.exec(statement).first()
        sequence = (latest.sequence_number if latest else 0) + 1
        message = Message(
            session_id=session_id,
            conversation_id=session_record.conversation_id,
            role=role,
            status="committed",
            sequence_number=sequence,
            content_text=content,
        )
        self.session.add(message)
        self.session.flush()
        return message

    def touch_session(self, session_record: SessionRecord) -> None:
        session_record.last_message_at = utc_now()
        session_record.updated_at = utc_now()
        self.session.add(session_record)
        self.session.flush()

    def list_skill_documents(self, agent_id: str) -> list[Document]:
        statement = select(Document).where(
            Document.agent_id == agent_id,
            Document.content_type == "application/vnd.nanobot.skill+markdown",
            Document.status == "active",
        )
        return list(self.session.exec(statement))

    def list_tool_permissions(self, agent_id: str) -> list[ToolPermission]:
        statement = select(ToolPermission).where(
            ToolPermission.agent_id == agent_id,
            ToolPermission.status == "active",
        )
        return list(self.session.exec(statement))

    def list_settings(self) -> list[Setting]:
        statement = select(Setting).where(Setting.status == "active")
        return list(self.session.exec(statement))

    def create_task(
        self,
        agent_id: str,
        session_id: str,
        payload: dict[str, object],
        *,
        title: str = "Agent simple execution",
        kind: str = "agent_execution",
        status: str = "running",
    ) -> Task:
        task = Task(
            agent_id=agent_id,
            session_id=session_id,
            title=title,
            kind=kind,
            status=status,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        self.session.add(task)
        self.session.flush()
        return task

    def create_task_run(
        self,
        task_id: str,
        *,
        status: str = "running",
        started_at=None,
    ) -> TaskRun:
        run = TaskRun(
            task_id=task_id,
            status=status,
            attempt=1,
            started_at=(
                started_at
                if started_at is not None
                else (None if status == "queued" else utc_now())
            ),
        )
        self.session.add(run)
        self.session.flush()
        return run

    def complete_task_run(
        self,
        task_run: TaskRun,
        *,
        status: str,
        output_json: str | None,
        error_message: str | None = None,
        estimated_cost_usd: float | None = None,
    ) -> TaskRun:
        task_run.status = status
        task_run.output_json = output_json
        task_run.error_message = error_message
        task_run.finished_at = utc_now()
        if task_run.started_at is not None:
            task_run.duration_ms = int(
                (ensure_utc(task_run.finished_at) - ensure_utc(task_run.started_at)).total_seconds()
                * 1000
            )
        task_run.estimated_cost_usd = estimated_cost_usd
        task_run.updated_at = utc_now()
        self.session.add(task_run)
        self.session.flush()
        return task_run

    def complete_task(self, task: Task, *, status: str) -> Task:
        task.status = status
        task.completed_at = utc_now()
        task.updated_at = utc_now()
        self.session.add(task)
        self.session.flush()
        return task

    def update_task_status(self, task: Task, *, status: str) -> Task:
        task.status = status
        task.updated_at = utc_now()
        self.session.add(task)
        self.session.flush()
        return task

    def update_task_run_status(
        self,
        task_run: TaskRun,
        *,
        status: str,
        output_json: str | None = None,
        error_message: str | None = None,
        estimated_cost_usd: float | None = None,
    ) -> TaskRun:
        task_run.status = status
        task_run.output_json = output_json
        task_run.error_message = error_message
        task_run.estimated_cost_usd = estimated_cost_usd
        task_run.updated_at = utc_now()
        self.session.add(task_run)
        self.session.flush()
        return task_run

    def claim_next_queued_execution_run(self) -> tuple[Task, TaskRun] | None:
        while True:
            candidate = self.session.exec(
                select(TaskRun.id, Task.id)
                .join(Task, Task.id == TaskRun.task_id)
                .where(
                    Task.kind == "agent_execution_async",
                    TaskRun.status == "queued",
                )
                .order_by(TaskRun.created_at.asc())
            ).first()
            if candidate is None:
                return None

            task_run_id, task_id = candidate
            now = utc_now()
            result = self.session.exec(
                update(TaskRun)
                .where(TaskRun.id == task_run_id, TaskRun.status == "queued")
                .values(status="running", started_at=now, updated_at=now)
            )
            if result.rowcount != 1:
                continue

            task = self.get_task(str(task_id))
            task_run = self.get_task_run(str(task_run_id))
            if task is None or task_run is None:
                return None
            task.status = "running"
            task.updated_at = now
            self.session.add(task)
            self.session.flush()
            return task, task_run

    def record_audit_event(
        self,
        *,
        agent_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, str | None],
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
        self.session.flush()
        return event
