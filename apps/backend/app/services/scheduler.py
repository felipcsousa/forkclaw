from __future__ import annotations

import asyncio
from datetime import UTC

from app.core.config import Settings
from app.core.schedules import parse_schedule
from app.db.session import get_db_session
from app.models.entities import utc_now
from app.repositories.cron_jobs import CronJobRepository
from app.services.cron_jobs import BackgroundTaskExecutor


class LocalScheduler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._last_heartbeat_started_at = 0.0

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task

    async def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.to_thread(self.tick)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.settings.scheduler_poll_interval_seconds,
                )
            except TimeoutError:
                continue

    def tick(self) -> None:
        with get_db_session() as session:
            repository = CronJobRepository(session)
            executor = BackgroundTaskExecutor(session)
            agent = repository.get_default_agent()
            if agent is None:
                return

            now = utc_now()
            self._repair_schedules(repository, agent.id, now)

            due_jobs = repository.list_due_jobs(agent.id, now)
            for job in due_jobs:
                executor.run_job(job)

            last_heartbeat = repository.get_setting("heartbeat", "last_run_at")
            if self._heartbeat_due(last_heartbeat.value_text if last_heartbeat else None):
                executor.run_heartbeat(
                    stale_after_seconds=self.settings.stale_task_run_seconds,
                )

    def _repair_schedules(self, repository: CronJobRepository, agent_id: str, now) -> None:
        for job in repository.list_cron_jobs(agent_id):
            if job.status != "active":
                continue
            if job.next_run_at is None:
                parsed = parse_schedule(job.schedule, job.timezone)
                job.next_run_at = parsed.next_after(reference_utc=now, last_run_at=job.last_run_at)
                repository.save_cron_job(job)

    def _heartbeat_due(self, last_run_at: str | None) -> bool:
        if not last_run_at:
            return True
        try:
            from datetime import datetime

            parsed = datetime.fromisoformat(last_run_at)
        except ValueError:
            return True
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return (utc_now() - parsed).total_seconds() >= self.settings.heartbeat_interval_seconds
