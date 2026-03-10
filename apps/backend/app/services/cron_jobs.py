from __future__ import annotations

import json
from datetime import timedelta

from sqlmodel import Session

from app.core.schedules import parse_schedule
from app.models.entities import CronJob, TaskRun, utc_now
from app.repositories.cron_jobs import CronJobRepository
from app.schemas.cron_job import (
    CronJobCreate,
    CronJobPayload,
    CronJobRead,
    CronJobsDashboardResponse,
    CronJobUpdate,
    HeartbeatStatusRead,
    TaskRunHistoryRead,
)


class CronJobService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = CronJobRepository(session)

    def get_dashboard(self) -> CronJobsDashboardResponse:
        agent = self.repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        jobs = [self._serialize_job(item) for item in self.repository.list_cron_jobs(agent.id)]
        history = [
            self._serialize_run(task_run, task, job)
            for task_run, task, job in self.repository.list_recent_runs(agent.id)
        ]
        heartbeat = self._heartbeat_status(agent.id, history)
        return CronJobsDashboardResponse(items=jobs, history=history, heartbeat=heartbeat)

    def create_job(self, payload: CronJobCreate) -> CronJobRead:
        agent = self.repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        timezone = payload.timezone or self._default_timezone()
        parsed = parse_schedule(payload.schedule, timezone)
        job = self.repository.create_cron_job(
            agent_id=agent.id,
            name=payload.name.strip(),
            schedule=parsed.schedule,
            timezone=timezone,
            payload_json=payload.payload.model_dump_json(),
            next_run_at=parsed.next_after(reference_utc=utc_now()),
        )
        self.repository.get_or_create_job_task(job)
        self.repository.record_audit_event(
            agent_id=agent.id,
            event_type="cron_job.created",
            entity_type="cron_job",
            entity_id=job.id,
            payload={"schedule": job.schedule, "timezone": job.timezone},
        )
        return self._serialize_job(job)

    def update_job(self, job_id: str, payload: CronJobUpdate) -> CronJobRead:
        job = self._require_job(job_id)
        if payload.name is not None:
            job.name = payload.name.strip()
        if payload.timezone is not None:
            job.timezone = payload.timezone
        if payload.schedule is not None:
            job.schedule = payload.schedule.strip().lower()
        if payload.payload is not None:
            job.task_payload_json = payload.payload.model_dump_json()

        parsed = parse_schedule(job.schedule, job.timezone)
        job.schedule = parsed.schedule
        if job.status == "active":
            job.next_run_at = parsed.next_after(
                reference_utc=utc_now(),
                last_run_at=job.last_run_at,
            )
        saved = self.repository.save_cron_job(job)
        self.repository.get_or_create_job_task(saved)
        self.repository.record_audit_event(
            agent_id=job.agent_id,
            event_type="cron_job.updated",
            entity_type="cron_job",
            entity_id=job.id,
            payload={"schedule": saved.schedule, "status": saved.status},
        )
        return self._serialize_job(saved)

    def pause_job(self, job_id: str) -> CronJobRead:
        job = self._require_job(job_id)
        job.status = "paused"
        job.next_run_at = None
        saved = self.repository.save_cron_job(job)
        self.repository.record_audit_event(
            agent_id=job.agent_id,
            event_type="cron_job.paused",
            entity_type="cron_job",
            entity_id=job.id,
            payload={},
        )
        return self._serialize_job(saved)

    def activate_job(self, job_id: str) -> CronJobRead:
        job = self._require_job(job_id)
        parsed = parse_schedule(job.schedule, job.timezone)
        job.status = "active"
        job.next_run_at = parsed.next_after(reference_utc=utc_now(), last_run_at=job.last_run_at)
        saved = self.repository.save_cron_job(job)
        self.repository.record_audit_event(
            agent_id=job.agent_id,
            event_type="cron_job.activated",
            entity_type="cron_job",
            entity_id=job.id,
            payload={"next_run_at": saved.next_run_at.isoformat() if saved.next_run_at else None},
        )
        return self._serialize_job(saved)

    def remove_job(self, job_id: str) -> None:
        job = self._require_job(job_id)
        job.status = "removed"
        job.next_run_at = None
        self.repository.save_cron_job(job)
        self.repository.record_audit_event(
            agent_id=job.agent_id,
            event_type="cron_job.removed",
            entity_type="cron_job",
            entity_id=job.id,
            payload={},
        )

    def _require_job(self, job_id: str) -> CronJob:
        job = self.repository.get_cron_job(job_id)
        if job is None or job.status == "removed":
            msg = "Cron job not found."
            raise ValueError(msg)
        return job

    def _default_timezone(self) -> str:
        setting = self.repository.get_setting("app", "timezone")
        return setting.value_text if setting and setting.value_text else "UTC"

    def _serialize_job(self, job: CronJob) -> CronJobRead:
        payload = CronJobPayload.model_validate_json(
            job.task_payload_json or '{"job_type":"summarize_recent_activity"}'
        )
        return CronJobRead(
            id=job.id,
            agent_id=job.agent_id,
            name=job.name,
            schedule=job.schedule,
            timezone=job.timezone,
            status=job.status,
            task_payload_json=job.task_payload_json,
            last_run_at=job.last_run_at,
            next_run_at=job.next_run_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
            payload=payload,
        )

    def _heartbeat_status(
        self,
        agent_id: str,
        history: list[TaskRunHistoryRead],
    ) -> HeartbeatStatusRead:
        last_run_at = None
        last_task_run_id = None
        for item in history:
            if item.task_kind == "heartbeat":
                last_run_at = item.finished_at or item.started_at
                last_task_run_id = item.task_run_id
                break

        summary_setting = self.repository.get_setting("heartbeat", "last_summary")
        payload = (
            json.loads(summary_setting.value_json)
            if summary_setting and summary_setting.value_json
            else {}
        )

        return HeartbeatStatusRead(
            last_run_at=last_run_at,
            task_run_id=last_task_run_id,
            cleaned_stale_runs=int(payload.get("cleaned_stale_runs", 0)),
            pending_approvals=int(payload.get("pending_approvals", 0)),
            recent_task_runs=int(payload.get("recent_task_runs", 0)),
            summary_text=str(payload.get("summary_text", "Heartbeat has not run yet.")),
        )

    def _serialize_run(self, task_run: TaskRun, task, job) -> TaskRunHistoryRead:
        output_summary = None
        if task_run.output_json:
            try:
                payload = json.loads(task_run.output_json)
            except json.JSONDecodeError:
                output_summary = task_run.output_json
            else:
                output_summary = str(payload.get("summary_text") or payload.get("message") or "")

        return TaskRunHistoryRead(
            task_run_id=task_run.id,
            task_id=task.id,
            cron_job_id=task.cron_job_id,
            task_title=task.title,
            task_kind=task.kind,
            task_status=task.status,
            job_name=job.name if job is not None else None,
            status=task_run.status,
            started_at=task_run.started_at,
            finished_at=task_run.finished_at,
            error_message=task_run.error_message,
            output_summary=output_summary,
            created_at=task_run.created_at,
        )


class BackgroundTaskExecutor:
    def __init__(self, session: Session):
        self.session = session
        self.repository = CronJobRepository(session)

    def run_job(self, job: CronJob) -> TaskRun:
        task = self.repository.get_or_create_job_task(job)
        task.payload_json = job.task_payload_json
        task.title = job.name
        self.repository.session.add(task)
        self.repository.session.commit()
        self.repository.session.refresh(task)

        task_run = self.repository.create_task_run(task)
        payload = CronJobPayload.model_validate_json(
            job.task_payload_json or '{"job_type":"summarize_recent_activity"}'
        )

        try:
            output = self._execute_payload(agent_id=job.agent_id, payload=payload)
            completed = self.repository.complete_task_run(
                task=task,
                task_run=task_run,
                status="completed",
                output_payload=output,
            )
            job.last_run_at = completed.finished_at
            job.next_run_at = parse_schedule(job.schedule, job.timezone).next_after(
                reference_utc=job.last_run_at or utc_now(),
                last_run_at=job.last_run_at,
            )
            self.repository.save_cron_job(job)
            self.repository.record_audit_event(
                agent_id=job.agent_id,
                event_type="cron_job.executed",
                entity_type="cron_job",
                entity_id=job.id,
                payload={"task_run_id": completed.id, "status": completed.status},
            )
            return completed
        except Exception as exc:
            failed = self.repository.complete_task_run(
                task=task,
                task_run=task_run,
                status="failed",
                output_payload={"summary_text": f"Job failed: {exc}"},
                error_message=str(exc),
            )
            job.last_run_at = failed.finished_at
            job.next_run_at = parse_schedule(job.schedule, job.timezone).next_after(
                reference_utc=job.last_run_at or utc_now(),
                last_run_at=job.last_run_at,
            )
            self.repository.save_cron_job(job)
            self.repository.record_audit_event(
                agent_id=job.agent_id,
                event_type="cron_job.failed",
                entity_type="cron_job",
                entity_id=job.id,
                payload={"task_run_id": failed.id, "error": str(exc)},
            )
            return failed

    def run_heartbeat(self, *, stale_after_seconds: int) -> TaskRun:
        agent = self.repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        task = self.repository.get_or_create_heartbeat_task(agent.id)
        task_run = self.repository.create_task_run(task)

        try:
            output = self._execute_heartbeat(agent.id, stale_after_seconds=stale_after_seconds)
            completed = self.repository.complete_task_run(
                task=task,
                task_run=task_run,
                status="completed",
                output_payload=output,
            )
            self.repository.upsert_setting(
                scope="heartbeat",
                key="last_summary",
                value_type="json",
                value_json=json.dumps(output, ensure_ascii=False),
            )
            self.repository.upsert_setting(
                scope="heartbeat",
                key="last_run_at",
                value_type="string",
                value_text=(completed.finished_at or utc_now()).isoformat(),
            )
            self.repository.record_audit_event(
                agent_id=agent.id,
                event_type="heartbeat.completed",
                entity_type="task_run",
                entity_id=completed.id,
                payload=output,
            )
            return completed
        except Exception as exc:
            failed = self.repository.complete_task_run(
                task=task,
                task_run=task_run,
                status="failed",
                output_payload={"summary_text": f"Heartbeat failed: {exc}"},
                error_message=str(exc),
            )
            self.repository.record_audit_event(
                agent_id=agent.id,
                event_type="heartbeat.failed",
                entity_type="task_run",
                entity_id=failed.id,
                payload={"error": str(exc)},
            )
            return failed

    def _execute_payload(self, *, agent_id: str, payload: CronJobPayload) -> dict[str, object]:
        since = utc_now() - timedelta(hours=24)

        if payload.job_type == "review_pending_approvals":
            pending = self.repository.count_pending_approvals(agent_id)
            summary = f"Pending approvals: {pending}."
            if payload.message:
                summary = f"{summary} {payload.message}"
            return {
                "job_type": payload.job_type,
                "pending_approvals": pending,
                "summary_text": summary,
            }

        if payload.job_type == "summarize_recent_activity":
            sessions = self.repository.count_recent_sessions(agent_id, since)
            messages = self.repository.count_recent_messages(since)
            tool_calls = self.repository.count_recent_tool_calls(since)
            task_runs = self.repository.count_recent_task_runs(agent_id, since)
            summary = (
                f"Recent activity in the last 24h: {sessions} sessions, {messages} messages, "
                f"{tool_calls} tool calls, {task_runs} task runs."
            )
            if payload.message:
                summary = f"{summary} {payload.message}"
            return {
                "job_type": payload.job_type,
                "sessions": sessions,
                "messages": messages,
                "tool_calls": tool_calls,
                "task_runs": task_runs,
                "summary_text": summary,
            }

        stale_after = payload.stale_after_seconds or 900
        cleaned = self._clean_stale_runs(stale_after_seconds=stale_after)
        summary = f"Cleaned {cleaned} stale running task runs older than {stale_after} seconds."
        if payload.message:
            summary = f"{summary} {payload.message}"
        return {
            "job_type": payload.job_type,
            "cleaned_stale_runs": cleaned,
            "stale_after_seconds": stale_after,
            "summary_text": summary,
        }

    def _execute_heartbeat(self, agent_id: str, *, stale_after_seconds: int) -> dict[str, object]:
        cleaned = self._clean_stale_runs(stale_after_seconds=stale_after_seconds)
        since = utc_now() - timedelta(hours=24)
        pending = self.repository.count_pending_approvals(agent_id)
        recent_runs = self.repository.count_recent_task_runs(agent_id, since)
        summary = (
            f"Heartbeat reviewed {recent_runs} recent task runs, "
            f"found {pending} pending approvals, "
            f"and cleaned {cleaned} stale runs."
        )
        return {
            "cleaned_stale_runs": cleaned,
            "pending_approvals": pending,
            "recent_task_runs": recent_runs,
            "summary_text": summary,
            "recorded_at": utc_now().isoformat(),
        }

    def _clean_stale_runs(self, *, stale_after_seconds: int) -> int:
        cutoff = utc_now() - timedelta(seconds=stale_after_seconds)
        stale_runs = self.repository.list_stale_running_runs(cutoff)
        for task_run, task in stale_runs:
            self.repository.complete_task_run(
                task=task,
                task_run=task_run,
                status="failed",
                output_payload={
                    "summary_text": "Marked as failed by heartbeat after stale timeout.",
                    "stale_after_seconds": stale_after_seconds,
                },
                error_message="Marked as failed by heartbeat after stale timeout.",
            )
        return len(stale_runs)
