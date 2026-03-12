from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, select

from app.models.entities import (
    Agent,
    Approval,
    AuditEvent,
    CronJob,
    Message,
    SessionRecord,
    Setting,
    Task,
    TaskRun,
    ToolCall,
    ensure_utc,
    utc_now,
)


class CronJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_setting(self, scope: str, key: str) -> Setting | None:
        statement = select(Setting).where(
            Setting.scope == scope,
            Setting.key == key,
            Setting.status == "active",
        )
        return self.session.exec(statement).first()

    def get_default_agent(self) -> Agent | None:
        statement = select(Agent).where(Agent.is_default.is_(True)).order_by(Agent.created_at.asc())
        return self.session.exec(statement).first()

    def list_cron_jobs(self, agent_id: str) -> list[CronJob]:
        statement = (
            select(CronJob)
            .where(CronJob.agent_id == agent_id, CronJob.status != "removed")
            .order_by(CronJob.created_at.asc())
        )
        return list(self.session.exec(statement))

    def get_cron_job(self, job_id: str) -> CronJob | None:
        statement = select(CronJob).where(CronJob.id == job_id)
        return self.session.exec(statement).first()

    def create_cron_job(
        self,
        *,
        agent_id: str,
        name: str,
        schedule: str,
        timezone: str,
        payload_json: str,
        next_run_at: datetime,
    ) -> CronJob:
        job = CronJob(
            agent_id=agent_id,
            name=name,
            schedule=schedule,
            timezone=timezone,
            status="active",
            task_payload_json=payload_json,
            next_run_at=next_run_at,
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def save_cron_job(self, job: CronJob) -> CronJob:
        job.updated_at = utc_now()
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_or_create_job_task(self, job: CronJob) -> Task:
        statement = select(Task).where(Task.cron_job_id == job.id).order_by(Task.created_at.asc())
        existing = self.session.exec(statement).first()
        if existing is not None:
            if existing.title != job.name:
                existing.title = job.name
                existing.updated_at = utc_now()
                self.session.add(existing)
                self.session.commit()
                self.session.refresh(existing)
            return existing

        task = Task(
            agent_id=job.agent_id,
            cron_job_id=job.id,
            session_id=None,
            title=job.name,
            kind="cron_job",
            status="idle",
            payload_json=job.task_payload_json,
        )
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_or_create_heartbeat_task(self, agent_id: str) -> Task:
        statement = (
            select(Task)
            .where(Task.agent_id == agent_id, Task.kind == "heartbeat")
            .order_by(Task.created_at.asc())
        )
        existing = self.session.exec(statement).first()
        if existing is not None:
            return existing

        task = Task(
            agent_id=agent_id,
            cron_job_id=None,
            session_id=None,
            title="Agent heartbeat",
            kind="heartbeat",
            status="idle",
            payload_json=None,
        )
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def create_task_run(self, task: Task) -> TaskRun:
        existing_runs = list(
            self.session.exec(
                select(TaskRun).where(TaskRun.task_id == task.id).order_by(TaskRun.created_at.asc())
            )
        )
        run = TaskRun(
            task_id=task.id,
            status="running",
            attempt=len(existing_runs) + 1,
            started_at=utc_now(),
        )
        task.status = "running"
        task.completed_at = None
        task.updated_at = utc_now()
        self.session.add(task)
        self.session.add(run)
        self.session.commit()
        self.session.refresh(task)
        self.session.refresh(run)
        return run

    def complete_task_run(
        self,
        *,
        task: Task,
        task_run: TaskRun,
        status: str,
        output_payload: dict[str, object] | None = None,
        error_message: str | None = None,
        estimated_cost_usd: float | None = None,
    ) -> TaskRun:
        task.status = status
        task.completed_at = utc_now()
        task.updated_at = utc_now()
        task_run.status = status
        task_run.finished_at = utc_now()
        if task_run.started_at is not None:
            task_run.duration_ms = int(
                (
                    ensure_utc(task_run.finished_at) - ensure_utc(task_run.started_at)
                ).total_seconds()
                * 1000
            )
        task_run.estimated_cost_usd = estimated_cost_usd
        task_run.error_message = error_message
        task_run.output_json = (
            json.dumps(output_payload, ensure_ascii=False) if output_payload is not None else None
        )
        task_run.updated_at = utc_now()
        self.session.add(task)
        self.session.add(task_run)
        self.session.commit()
        self.session.refresh(task)
        self.session.refresh(task_run)
        return task_run

    def list_due_jobs(self, agent_id: str, now: datetime) -> list[CronJob]:
        statement = (
            select(CronJob)
            .where(
                CronJob.agent_id == agent_id,
                CronJob.status == "active",
                CronJob.next_run_at.is_not(None),
                CronJob.next_run_at <= now,
            )
            .order_by(CronJob.next_run_at.asc())
        )
        return list(self.session.exec(statement))

    def list_recent_runs(
        self,
        agent_id: str,
        limit: int = 25,
    ) -> list[tuple[TaskRun, Task, CronJob | None]]:
        statement = (
            select(TaskRun, Task, CronJob)
            .join(Task, Task.id == TaskRun.task_id)
            .join(CronJob, CronJob.id == Task.cron_job_id, isouter=True)
            .where(Task.agent_id == agent_id, Task.kind.in_(["cron_job", "heartbeat"]))
            .order_by(TaskRun.created_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement))

    def count_pending_approvals(self, agent_id: str) -> int:
        statement = select(Approval).where(
            Approval.agent_id == agent_id,
            Approval.status == "pending",
        )
        return len(list(self.session.exec(statement)))

    def list_stale_running_runs(self, cutoff: datetime) -> list[tuple[TaskRun, Task]]:
        statement = (
            select(TaskRun, Task)
            .join(Task, Task.id == TaskRun.task_id)
            .where(
                TaskRun.status == "running",
                TaskRun.started_at.is_not(None),
                TaskRun.started_at <= cutoff,
                Task.kind.in_(["cron_job", "heartbeat"]),
            )
            .order_by(TaskRun.started_at.asc())
        )
        return list(self.session.exec(statement))

    def count_recent_sessions(self, agent_id: str, since: datetime) -> int:
        statement = select(SessionRecord).where(
            SessionRecord.agent_id == agent_id,
            SessionRecord.kind == "main",
            SessionRecord.created_at >= since,
        )
        return len(list(self.session.exec(statement)))

    def count_recent_messages(self, since: datetime) -> int:
        statement = select(Message).where(Message.created_at >= since)
        return len(list(self.session.exec(statement)))

    def count_recent_tool_calls(self, since: datetime) -> int:
        statement = select(ToolCall).where(ToolCall.created_at >= since)
        return len(list(self.session.exec(statement)))

    def count_recent_task_runs(self, agent_id: str, since: datetime) -> int:
        statement = (
            select(TaskRun)
            .join(Task, Task.id == TaskRun.task_id)
            .where(Task.agent_id == agent_id, TaskRun.created_at >= since)
        )
        return len(list(self.session.exec(statement)))

    def upsert_setting(
        self,
        *,
        scope: str,
        key: str,
        value_type: str,
        value_text: str | None = None,
        value_json: str | None = None,
    ) -> Setting:
        existing = self.get_setting(scope, key)
        if existing is None:
            existing = Setting(
                scope=scope,
                key=key,
                value_type=value_type,
                value_text=value_text,
                value_json=value_json,
                status="active",
            )
        else:
            existing.value_type = value_type
            existing.value_text = value_text
            existing.value_json = value_json
            existing.updated_at = utc_now()
        self.session.add(existing)
        self.session.commit()
        self.session.refresh(existing)
        return existing

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
