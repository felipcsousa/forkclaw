from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from app.models.entities import utc_now


@dataclass
class RuntimeComponentSnapshot:
    status: str
    poll_interval_seconds: float
    last_tick_started_at: datetime | None
    last_tick_finished_at: datetime | None
    last_success_at: datetime | None
    last_error_at: datetime | None
    consecutive_failures: int
    last_error_summary: str | None


class RuntimeComponentProbe:
    def __init__(self, *, name: str, poll_interval_seconds: float):
        self.name = name
        self.poll_interval_seconds = poll_interval_seconds
        self._lock = threading.Lock()
        self._snapshot = RuntimeComponentSnapshot(
            status="stopped",
            poll_interval_seconds=poll_interval_seconds,
            last_tick_started_at=None,
            last_tick_finished_at=None,
            last_success_at=None,
            last_error_at=None,
            consecutive_failures=0,
            last_error_summary=None,
        )

    def mark_starting(self) -> None:
        with self._lock:
            self._snapshot.status = "starting"
            self._snapshot.last_error_summary = None

    def mark_tick_started(self) -> None:
        with self._lock:
            self._snapshot.status = "running"
            self._snapshot.last_tick_started_at = utc_now()

    def mark_tick_succeeded(self) -> None:
        with self._lock:
            finished_at = utc_now()
            self._snapshot.status = "running"
            self._snapshot.last_tick_finished_at = finished_at
            self._snapshot.last_success_at = finished_at
            self._snapshot.consecutive_failures = 0
            self._snapshot.last_error_summary = None

    def mark_tick_failed(self, error: Exception) -> None:
        with self._lock:
            failed_at = utc_now()
            self._snapshot.status = "degraded"
            self._snapshot.last_tick_finished_at = failed_at
            self._snapshot.last_error_at = failed_at
            self._snapshot.consecutive_failures += 1
            self._snapshot.last_error_summary = str(error) or error.__class__.__name__

    def mark_stopped(self) -> None:
        with self._lock:
            self._snapshot.status = "stopped"

    def snapshot(self) -> RuntimeComponentSnapshot:
        with self._lock:
            return RuntimeComponentSnapshot(**self._snapshot.__dict__)
