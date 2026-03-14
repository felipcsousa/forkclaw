from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.entities import Approval, CronJob, SessionSubagentRun


class RuntimeHealthRepository:
    def __init__(self, session: Session):
        self.session = session

    def count_subagents_by_status(self, *statuses: str) -> int:
        statement = (
            select(func.count())
            .select_from(SessionSubagentRun)
            .where(SessionSubagentRun.lifecycle_status.in_(statuses))
        )
        return int(self.session.exec(statement).one())

    def count_active_cron_jobs(self) -> int:
        statement = select(func.count()).select_from(CronJob).where(CronJob.status == "active")
        return int(self.session.exec(statement).one())

    def count_due_cron_jobs(self, now: datetime) -> int:
        statement = (
            select(func.count())
            .select_from(CronJob)
            .where(
                CronJob.status == "active",
                CronJob.next_run_at.is_not(None),
                CronJob.next_run_at <= now,
            )
        )
        return int(self.session.exec(statement).one())

    def count_pending_approvals(self) -> int:
        statement = select(func.count()).select_from(Approval).where(Approval.status == "pending")
        return int(self.session.exec(statement).one())
