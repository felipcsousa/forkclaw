from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.db.session import get_db_session
from app.services.agent_execution import AgentExecutionService
from app.services.runtime_monitor import RuntimeComponentProbe


class LocalExecutionWorker:
    def __init__(self, settings: Settings, *, probe: RuntimeComponentProbe | None = None):
        self.settings = settings
        self.probe = probe
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            if self.probe is not None:
                self.probe.mark_starting()
            self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None
        if self.probe is not None:
            self.probe.mark_stopped()

    async def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.probe is not None:
                    self.probe.mark_tick_started()
                await asyncio.to_thread(self.tick)
            except Exception as exc:
                if self.probe is not None:
                    self.probe.mark_tick_failed(exc)
            else:
                if self.probe is not None:
                    self.probe.mark_tick_succeeded()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.settings.execution_worker_poll_interval_seconds,
                )
            except TimeoutError:
                continue

    def tick(self) -> None:
        with get_db_session() as session:
            service = AgentExecutionService(session)
            service.process_next_queued_execution()
