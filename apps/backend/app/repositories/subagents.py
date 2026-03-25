from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, update
from sqlmodel import Session, select

from app.models.entities import (
    AuditEvent,
    Memory,
    Message,
    SessionRecord,
    SessionSubagentRun,
    Task,
    TaskRun,
    ToolCall,
    ensure_utc,
    generate_id,
    utc_now,
)

TERMINAL_SUBAGENT_STATUSES = {"completed", "failed", "cancelled", "timed_out"}


class SubagentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_session(self, session_id: str) -> SessionRecord | None:
        statement = select(SessionRecord).where(SessionRecord.id == session_id)
        return self.session.exec(statement).first()

    def get_sessions(self, session_ids: Sequence[str]) -> list[SessionRecord]:
        statement = select(SessionRecord).where(SessionRecord.id.in_(session_ids))
        return list(self.session.exec(statement).all())

    def get_task(self, task_id: str | None) -> Task | None:
        if not task_id:
            return None
        statement = select(Task).where(Task.id == task_id)
        return self.session.exec(statement).first()

    def get_task_run(self, task_run_id: str | None) -> TaskRun | None:
        if not task_run_id:
            return None
        statement = select(TaskRun).where(TaskRun.id == task_run_id)
        return self.session.exec(statement).first()

    def get_message(self, message_id: str | None) -> Message | None:
        if not message_id:
            return None
        statement = select(Message).where(Message.id == message_id)
        return self.session.exec(statement).first()

    def create_subagent_session(
        self,
        *,
        agent_id: str,
        parent_session: SessionRecord,
        delegated_goal: str,
        delegated_context_snapshot: str | None,
        tool_profile: str | None,
        model_override: str | None,
        max_iterations: int | None,
        timeout_seconds: float | None,
    ) -> SessionRecord:
        child = SessionRecord(
            agent_id=agent_id,
            kind="subagent",
            parent_session_id=parent_session.id,
            root_session_id=parent_session.root_session_id or parent_session.id,
            spawn_depth=parent_session.spawn_depth + 1,
            title=self._subagent_title(delegated_goal),
            summary=None,
            conversation_id=generate_id(),
            status="queued",
            delegated_goal=delegated_goal,
            delegated_context_snapshot=delegated_context_snapshot,
            tool_profile=tool_profile,
            model_override=model_override,
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds,
            started_at=utc_now(),
        )
        self.session.add(child)
        self.session.flush()
        return child

    def create_subagent_run(
        self,
        *,
        launcher_session_id: str,
        child_session_id: str,
        launcher_message_id: str | None = None,
        launcher_task_run_id: str | None = None,
    ) -> SessionSubagentRun:
        run = SessionSubagentRun(
            launcher_session_id=launcher_session_id,
            child_session_id=child_session_id,
            launcher_message_id=launcher_message_id,
            launcher_task_run_id=launcher_task_run_id,
            lifecycle_status="queued",
        )
        self.session.add(run)
        self.session.flush()
        return run

    def spawn_subagent(
        self,
        *,
        parent_session_id: str,
        delegated_goal: str,
        delegated_context_snapshot: str | None,
        tool_profile: str | None,
        model_override: str | None,
        max_iterations: int | None,
        timeout_seconds: float,
        max_concurrency: int,
        launcher_message_id: str | None = None,
        launcher_task_run_id: str | None = None,
    ) -> tuple[SessionRecord, SessionRecord, SessionSubagentRun]:
        parent = self.get_session(parent_session_id)
        if parent is None:
            msg = "Session not found."
            raise ValueError(msg)
        if parent.kind != "main":
            msg = "Only main sessions can spawn subagents."
            raise ValueError(msg)
        if parent.spawn_depth > 0:
            msg = "Subagent spawn depth cannot exceed 1."
            raise ValueError(msg)
        active_runs = self.count_active_runs(parent.id)
        if active_runs >= max_concurrency:
            msg = f"Subagent concurrency limit reached for this session ({max_concurrency})."
            raise ValueError(msg)
        child = self.create_subagent_session(
            agent_id=parent.agent_id,
            parent_session=parent,
            delegated_goal=delegated_goal,
            delegated_context_snapshot=delegated_context_snapshot,
            tool_profile=tool_profile,
            model_override=model_override,
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds,
        )
        run = self.create_subagent_run(
            launcher_session_id=parent.id,
            child_session_id=child.id,
            launcher_message_id=launcher_message_id,
            launcher_task_run_id=launcher_task_run_id,
        )
        self.session.flush()
        return parent, child, run

    def refresh(self, record: SessionRecord | SessionSubagentRun) -> None:
        self.session.refresh(record)

    def count_active_runs(self, launcher_session_id: str) -> int:
        statement = select(func.count(SessionSubagentRun.id)).where(
            SessionSubagentRun.launcher_session_id == launcher_session_id,
            SessionSubagentRun.lifecycle_status.in_(["queued", "running"]),
        )
        return int(self.session.exec(statement).one())

    def list_subagents(
        self,
        parent_session_id: str,
    ) -> list[tuple[SessionRecord, SessionSubagentRun]]:
        statement = (
            select(SessionRecord, SessionSubagentRun)
            .join(
                SessionSubagentRun,
                SessionSubagentRun.child_session_id == SessionRecord.id,
            )
            .where(SessionRecord.parent_session_id == parent_session_id)
            .order_by(SessionRecord.created_at.desc())
        )
        return list(self.session.exec(statement))

    def list_recent_messages(
        self,
        session_id: str,
        *,
        limit: int = 4,
    ) -> list[Message]:
        session_record = self.get_session(session_id)
        if session_record is None:
            return []
        statement = (
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.conversation_id == session_record.conversation_id,
            )
            .order_by(Message.sequence_number.desc())
            .limit(limit)
        )
        return list(reversed(list(self.session.exec(statement))))

    def list_messages(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before_sequence: int | None = None,
    ) -> tuple[list[Message], bool, int | None]:
        session_record = self.get_session(session_id)
        if session_record is None:
            return [], False, None

        statement = select(Message).where(
            Message.session_id == session_id,
            Message.conversation_id == session_record.conversation_id,
        )
        if before_sequence is not None:
            statement = statement.where(Message.sequence_number < before_sequence)

        if limit is None:
            statement = statement.order_by(Message.sequence_number.asc())
            return list(self.session.exec(statement)), False, None

        rows = list(
            self.session.exec(statement.order_by(Message.sequence_number.desc()).limit(limit + 1))
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        page.reverse()
        next_before_sequence = page[0].sequence_number if has_more and page else None
        return page, has_more, next_before_sequence

    def get_subagent(
        self,
        *,
        parent_session_id: str,
        child_session_id: str,
    ) -> tuple[SessionRecord, SessionSubagentRun] | None:
        statement = (
            select(SessionRecord, SessionSubagentRun)
            .join(
                SessionSubagentRun,
                SessionSubagentRun.child_session_id == SessionRecord.id,
            )
            .where(
                SessionRecord.parent_session_id == parent_session_id,
                SessionRecord.id == child_session_id,
            )
        )
        return self.session.exec(statement).first()

    def aggregate_counts_by_launcher_session(
        self,
        launcher_session_ids: Sequence[str],
    ) -> dict[str, dict[str, int]]:
        if not launcher_session_ids:
            return {}

        statement = (
            select(
                SessionSubagentRun.launcher_session_id,
                SessionSubagentRun.lifecycle_status,
                func.count(SessionSubagentRun.id),
            )
            .where(SessionSubagentRun.launcher_session_id.in_(launcher_session_ids))
            .group_by(
                SessionSubagentRun.launcher_session_id,
                SessionSubagentRun.lifecycle_status,
            )
        )
        counts: dict[str, dict[str, int]] = {}
        for launcher_session_id, lifecycle_status, total in self.session.exec(statement):
            item = counts.setdefault(
                launcher_session_id,
                {
                    "total": 0,
                    "queued": 0,
                    "running": 0,
                    "completed": 0,
                    "failed": 0,
                    "cancelled": 0,
                    "timed_out": 0,
                },
            )
            item["total"] += int(total)
            if lifecycle_status in item:
                item[lifecycle_status] += int(total)
        return counts

    def request_cancellation(self, run: SessionSubagentRun) -> SessionSubagentRun:
        if run.lifecycle_status != "running":
            return run
        run.cancellation_requested_at = utc_now()
        run.updated_at = utc_now()
        self.session.add(run)
        self.session.flush()
        return run

    def claim_next_queued_run(self) -> SessionSubagentRun | None:
        while True:
            candidate_id = self.session.exec(
                select(SessionSubagentRun.id)
                .where(SessionSubagentRun.lifecycle_status == "queued")
                .order_by(SessionSubagentRun.created_at.asc())
            ).first()
            if candidate_id is None:
                return None
            now = utc_now()
            result = self.session.exec(
                update(SessionSubagentRun)
                .where(
                    SessionSubagentRun.id == candidate_id,
                    SessionSubagentRun.lifecycle_status == "queued",
                )
                .values(
                    lifecycle_status="running",
                    started_at=now,
                    updated_at=now,
                )
            )
            if result.rowcount == 1:
                self.session.flush()
                return self.get_run(str(candidate_id))

    def get_run(self, run_id: str) -> SessionSubagentRun | None:
        statement = select(SessionSubagentRun).where(SessionSubagentRun.id == run_id)
        return self.session.exec(statement).first()

    def attach_execution_ids(
        self,
        run: SessionSubagentRun,
        *,
        task_id: str,
        task_run_id: str,
    ) -> SessionSubagentRun:
        run.task_id = task_id
        run.task_run_id = task_run_id
        run.updated_at = utc_now()
        self.session.add(run)
        self.session.flush()
        return run

    def finalize_run(
        self,
        *,
        run_id: str,
        status: str,
        final_summary: str,
        final_output_json: str,
        estimated_cost_usd: float | None,
        error_code: str | None,
        error_summary: str | None,
        parent_message_text: str,
        terminal_event_type: str,
        terminal_event_payload: dict[str, Any],
        terminal_event_summary: str,
    ) -> SessionSubagentRun:
        run = self.get_run(run_id)
        if run is None:
            msg = "Subagent run not found."
            raise ValueError(msg)
        child = self.get_session(run.child_session_id)
        parent = self.get_session(run.launcher_session_id)
        if child is None or parent is None:
            msg = "Subagent run is missing its session lineage."
            raise ValueError(msg)
        if run.lifecycle_status in TERMINAL_SUBAGENT_STATUSES:
            return run

        now = utc_now()
        resolved_status = status
        if run.cancellation_requested_at is not None and status != "timed_out":
            resolved_status = "cancelled"
        run.lifecycle_status = resolved_status
        run.finished_at = now
        run.final_summary = final_summary
        run.final_output_json = final_output_json
        run.estimated_cost_usd = estimated_cost_usd
        run.error_code = error_code
        run.error_summary = error_summary
        run.updated_at = now

        child.status = resolved_status
        child.summary = final_summary
        child.updated_at = now

        summary_message = self._create_message_no_commit(
            session_id=parent.id,
            role="assistant",
            content=parent_message_text,
        )
        parent.last_message_at = summary_message.created_at
        parent.updated_at = now
        run.parent_summary_message_id = summary_message.id

        self._sync_task_state_for_terminal_subagent(
            run=run,
            resolved_status=resolved_status,
            final_output_json=final_output_json,
            estimated_cost_usd=estimated_cost_usd,
            error_summary=error_summary,
            finished_at=now,
        )
        self._record_audit_event_no_commit(
            agent_id=child.agent_id,
            event_type=terminal_event_type,
            entity_type="session_subagent_run",
            entity_id=run.id,
            payload=terminal_event_payload,
            summary_text=terminal_event_summary,
        )

        self.session.add(child)
        self.session.add(parent)
        self.session.add(run)
        self.session.flush()
        return run

    def list_running_subagents(
        self,
    ) -> list[tuple[SessionSubagentRun, SessionRecord, SessionRecord]]:
        running_runs = list(
            self.session.exec(
                select(SessionSubagentRun)
                .where(SessionSubagentRun.lifecycle_status == "running")
                .order_by(SessionSubagentRun.started_at.asc(), SessionSubagentRun.created_at.asc())
            )
        )

        session_ids = set()
        for run in running_runs:
            session_ids.add(run.child_session_id)
            session_ids.add(run.launcher_session_id)

        sessions = {s.id: s for s in self.get_sessions(list(session_ids))}

        items: list[tuple[SessionSubagentRun, SessionRecord, SessionRecord]] = []
        for run in running_runs:
            child = sessions.get(run.child_session_id)
            parent = sessions.get(run.launcher_session_id)
            if child is None or parent is None:
                continue
            items.append((run, child, parent))
        return items

    def should_cancel_run(self, run_id: str) -> bool:
        self.session.expire_all()
        run = self.get_run(run_id)
        if run is None:
            return True
        if run.lifecycle_status in TERMINAL_SUBAGENT_STATUSES:
            return True
        return run.cancellation_requested_at is not None

    def create_message(self, session_id: str, role: str, content: str) -> Message:
        message = self._create_message_no_commit(session_id=session_id, role=role, content=content)
        self.session.flush()
        return message

    def create_memory(
        self,
        *,
        agent_id: str,
        namespace: str,
        memory_key: str,
        value_text: str,
        source: str,
        memory_class: str,
        scope_kind: str,
        scope_ref: str | None,
        session_id: str | None,
        conversation_id: str | None,
        parent_session_id: str | None,
    ) -> Memory:
        memory = Memory(
            agent_id=agent_id,
            namespace=namespace,
            memory_key=memory_key,
            value_text=value_text,
            source=source,
            memory_class=memory_class,
            scope_kind=scope_kind,
            scope_ref=scope_ref,
            session_id=session_id,
            conversation_id=conversation_id,
            parent_session_id=parent_session_id,
            status="active",
        )
        self.session.add(memory)
        self.session.flush()
        return memory

    def touch_session(self, session_record: SessionRecord) -> None:
        session_record.last_message_at = utc_now()
        session_record.updated_at = utc_now()
        self.session.add(session_record)
        self.session.flush()

    def list_tool_calls_for_task_run(self, task_run_id: str | None) -> list[ToolCall]:
        if task_run_id is None:
            return []
        statement = (
            select(ToolCall)
            .where(ToolCall.task_run_id == task_run_id)
            .order_by(ToolCall.created_at.asc())
        )
        return list(self.session.exec(statement))

    def list_subagent_audit_events(
        self,
        *,
        run: SessionSubagentRun,
    ) -> list[AuditEvent]:
        entity_ids = [run.id, run.child_session_id]
        if run.task_id is not None:
            entity_ids.append(run.task_id)
        if run.task_run_id is not None:
            entity_ids.append(run.task_run_id)

        statement = (
            select(AuditEvent)
            .where(AuditEvent.entity_id.in_(entity_ids))
            .order_by(AuditEvent.created_at.asc())
        )
        return list(self.session.exec(statement))

    def record_audit_event(
        self,
        *,
        agent_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, Any],
        summary_text: str,
    ) -> AuditEvent:
        event = self._record_audit_event_no_commit(
            agent_id=agent_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            summary_text=summary_text,
        )
        self.session.flush()
        return event

    def _record_audit_event_no_commit(
        self,
        *,
        agent_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, Any],
        summary_text: str,
    ) -> AuditEvent:
        event = AuditEvent(
            agent_id=agent_id,
            actor_type="system",
            level="info",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            summary_text=summary_text,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        self.session.add(event)
        self.session.flush()
        return event

    def _create_message_no_commit(self, *, session_id: str, role: str, content: str) -> Message:
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

    def _sync_task_state_for_terminal_subagent(
        self,
        *,
        run: SessionSubagentRun,
        resolved_status: str,
        final_output_json: str,
        estimated_cost_usd: float | None,
        error_summary: str | None,
        finished_at,
    ) -> None:
        task = self.get_task(run.task_id)
        if task is not None:
            task.status = resolved_status
            task.completed_at = finished_at
            task.updated_at = finished_at
            self.session.add(task)

        task_run = self.get_task_run(run.task_run_id)
        if task_run is None:
            return

        task_run.status = resolved_status
        task_run.finished_at = finished_at
        if task_run.started_at is not None:
            task_run.duration_ms = int(
                (ensure_utc(finished_at) - ensure_utc(task_run.started_at)).total_seconds() * 1000
            )
        if estimated_cost_usd is not None:
            task_run.estimated_cost_usd = estimated_cost_usd
        if error_summary is not None and resolved_status in {"failed", "cancelled", "timed_out"}:
            task_run.error_message = error_summary
        if task_run.output_json is None and resolved_status in {"cancelled", "timed_out"}:
            task_run.output_json = final_output_json
        task_run.updated_at = finished_at
        self.session.add(task_run)

    @staticmethod
    def _subagent_title(goal: str) -> str:
        normalized = " ".join(goal.strip().split())
        if not normalized:
            return "Subagent"
        return normalized[:200]
