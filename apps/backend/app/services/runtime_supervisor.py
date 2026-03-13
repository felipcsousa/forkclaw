from __future__ import annotations

import logging
from collections.abc import Callable
from inspect import isawaitable
from typing import Any

from sqlmodel import Session

from app.core.config import Settings
from app.models.entities import utc_now
from app.repositories.runtime_health import RuntimeHealthRepository
from app.schemas.health import (
    OperationalBacklogHealthResponse,
    OperationalComponentHealthResponse,
    OperationalComponentsHealthResponse,
    OperationalHealthResponse,
)
from app.services.execution_worker import LocalExecutionWorker
from app.services.runtime_monitor import RuntimeComponentProbe, RuntimeComponentSnapshot
from app.services.scheduler import LocalScheduler
from app.services.subagent_worker import LocalSubagentWorker

logger = logging.getLogger("nanobot.runtime")


class RuntimeSupervisor:
    def __init__(
        self,
        settings: Settings,
        *,
        scheduler_factory: Callable[..., Any] = LocalScheduler,
        execution_worker_factory: Callable[..., Any] = LocalExecutionWorker,
        subagent_worker_factory: Callable[..., Any] = LocalSubagentWorker,
    ):
        self.settings = settings
        self.scheduler_probe = RuntimeComponentProbe(
            name="scheduler",
            poll_interval_seconds=settings.scheduler_poll_interval_seconds,
        )
        self.execution_worker_probe = RuntimeComponentProbe(
            name="execution_worker",
            poll_interval_seconds=settings.execution_worker_poll_interval_seconds,
        )
        self.subagent_worker_probe = RuntimeComponentProbe(
            name="subagent_worker",
            poll_interval_seconds=settings.subagent_worker_poll_interval_seconds,
        )
        self.scheduler = scheduler_factory(settings, probe=self.scheduler_probe)
        self.execution_worker = execution_worker_factory(
            settings,
            probe=self.execution_worker_probe,
        )
        self.subagent_worker = subagent_worker_factory(
            settings,
            probe=self.subagent_worker_probe,
        )

    async def start(self) -> None:
        await self._start_component(self.scheduler, self.scheduler_probe)
        await self._start_component(self.execution_worker, self.execution_worker_probe)
        await self._start_component(self.subagent_worker, self.subagent_worker_probe)

    async def stop(self) -> None:
        await self._stop_component(self.subagent_worker, self.subagent_worker_probe)
        await self._stop_component(self.execution_worker, self.execution_worker_probe)
        await self._stop_component(self.scheduler, self.scheduler_probe)

    def operational_health(self, session: Session) -> OperationalHealthResponse:
        repository = RuntimeHealthRepository(session)
        scheduler_snapshot = self.scheduler_probe.snapshot()
        execution_worker_snapshot = self.execution_worker_probe.snapshot()
        subagent_worker_snapshot = self.subagent_worker_probe.snapshot()
        status = (
            "ok"
            if scheduler_snapshot.status == "running"
            and execution_worker_snapshot.status == "running"
            and subagent_worker_snapshot.status == "running"
            else "degraded"
        )
        now = utc_now()
        return OperationalHealthResponse(
            status=status,
            service="backend",
            version="0.1.0",
            components=OperationalComponentsHealthResponse(
                scheduler=self._serialize_snapshot(scheduler_snapshot),
                execution_worker=self._serialize_snapshot(execution_worker_snapshot),
                subagent_worker=self._serialize_snapshot(subagent_worker_snapshot),
            ),
            backlog=OperationalBacklogHealthResponse(
                queued_subagents=repository.count_subagents_by_status("queued"),
                running_subagents=repository.count_subagents_by_status("running"),
                active_cron_jobs=repository.count_active_cron_jobs(),
                due_cron_jobs=repository.count_due_cron_jobs(now),
                pending_approvals=repository.count_pending_approvals(),
            ),
        )

    @staticmethod
    def _serialize_snapshot(
        snapshot: RuntimeComponentSnapshot,
    ) -> OperationalComponentHealthResponse:
        return OperationalComponentHealthResponse(
            status=snapshot.status,  # type: ignore[arg-type]
            poll_interval_seconds=snapshot.poll_interval_seconds,
            last_tick_started_at=snapshot.last_tick_started_at,
            last_tick_finished_at=snapshot.last_tick_finished_at,
            last_success_at=snapshot.last_success_at,
            last_error_at=snapshot.last_error_at,
            consecutive_failures=snapshot.consecutive_failures,
            last_error_summary=snapshot.last_error_summary,
        )

    async def _start_component(self, component: Any, probe: RuntimeComponentProbe) -> None:
        probe.mark_starting()
        try:
            result = component.start()
            if isawaitable(result):
                await result
        except Exception as exc:
            probe.mark_tick_failed(exc)
            logger.exception(
                "runtime.component_start_failed component=%s error=%s",
                probe.name,
                exc,
            )

    async def _stop_component(self, component: Any, probe: RuntimeComponentProbe) -> None:
        try:
            result = component.stop()
            if isawaitable(result):
                await result
        except Exception as exc:
            logger.exception("runtime.component_stop_failed component=%s error=%s", probe.name, exc)
        finally:
            probe.mark_stopped()
