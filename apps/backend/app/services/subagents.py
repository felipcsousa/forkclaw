from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar

from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from app.core.config import get_settings
from app.models.entities import SessionSubagentRun, ensure_utc, utc_now
from app.repositories.subagents import SubagentRepository
from app.schemas.session import (
    SessionSubagentsListResponse,
    SubagentCancelResponse,
    SubagentCountsRead,
    SubagentRunRead,
    SubagentSessionRead,
    SubagentSpawnRequest,
    SubagentSpawnResponse,
    SubagentTimelineEventRead,
)
from app.services.agent_execution import AgentExecutionService
from app.services.memory_capture_service import MemoryCaptureService
from app.services.subagent_completion import SubagentCompletionSummaryBuilder
from app.services.subagent_tool_scoping import resolve_subagent_tool_scope

PUBLIC_SUBAGENT_EVENT_TYPES = {
    "subagent.spawned",
    "subagent.started",
    "subagent.completed",
    "subagent.failed",
    "subagent.cancel_requested",
    "subagent.cancelled",
    "subagent.timed_out",
}

LEGACY_SUBAGENT_EVENT_TYPE_MAP = {
    "subagent.run.started": "subagent.started",
    "subagent.run.completed": "subagent.completed",
    "subagent.run.failed": "subagent.failed",
    "subagent.run.cancelled": "subagent.cancelled",
    "subagent.run.timed_out": "subagent.timed_out",
}

KNOWN_SUBAGENT_STATUSES = {
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "timed_out",
}

_T = TypeVar("_T")


class SubagentDelegationService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = SubagentRepository(session)
        self.execution_service = AgentExecutionService(session)
        self.memory_capture = MemoryCaptureService(session)
        self.summary_builder = SubagentCompletionSummaryBuilder()

    def spawn(
        self,
        *,
        parent_session_id: str,
        payload: SubagentSpawnRequest,
    ) -> SubagentSpawnResponse:
        parent = self._require_spawnable_parent(parent_session_id)
        settings = get_settings()
        goal = payload.goal.strip()
        goal_summary = self._goal_summary(goal)
        parent_messages = self.repository.list_recent_messages(parent.id)
        snapshot = self._build_parent_snapshot(parent_title=parent.title, messages=parent_messages)
        launcher_message_id = self._resolve_launcher_message_id(
            parent_session_id=parent.id,
            explicit_launcher_message_id=payload.launcher_message_id,
        )
        tool_permissions = self.execution_service.request_builder.list_active_tool_permissions(
            parent.agent_id
        )
        resolution = resolve_subagent_tool_scope(
            requested_toolsets=payload.toolsets,
            tool_permissions=tool_permissions,
        )
        timeout_seconds = self._normalize_timeout_seconds(payload.timeout_seconds)
        parent, child, _run = self._run_with_sqlite_retry(
            lambda: self._spawn_subagent_immediate(
                parent_session_id=parent.id,
                delegated_goal=goal,
                delegated_context_snapshot=self._build_context_snapshot(
                    explicit_context=payload.context,
                    parent_snapshot=snapshot,
                ),
                tool_profile=json.dumps(resolution.requested_toolsets, ensure_ascii=False),
                model_override=(payload.model or "").strip() or None,
                max_iterations=payload.max_iterations,
                timeout_seconds=timeout_seconds,
                max_concurrency=settings.subagent_max_concurrency_per_session,
                launcher_message_id=launcher_message_id,
                launcher_task_run_id=payload.launcher_task_run_id,
            )
        )
        self._commit_action(
            lambda: self.repository.record_audit_event(
                agent_id=parent.agent_id,
                event_type="subagent.spawned",
                entity_type="session",
                entity_id=child.id,
                payload=self._event_payload(
                    parent_session_id=parent.id,
                    child_session_id=child.id,
                    goal_summary=goal_summary,
                    status="queued",
                    extra={
                        "spawn_depth": child.spawn_depth,
                        "toolsets": resolution.requested_toolsets,
                        "empty_groups": resolution.empty_groups,
                        "timeout_seconds": timeout_seconds,
                    },
                ),
                summary_text="Subagent session spawned.",
            )
        )
        return SubagentSpawnResponse(
            parent_session_id=parent.id,
            child_session_id=child.id,
            status="accepted",
            spawn_depth=child.spawn_depth,
            toolsets=resolution.requested_toolsets,
            model=child.model_override,
            max_iterations=child.max_iterations,
            timeout_seconds=timeout_seconds,
        )

    def list(self, parent_session_id: str) -> SessionSubagentsListResponse:
        parent = self._require_main_parent(parent_session_id)
        items = [
            self._serialize_subagent(session_record, run)
            for session_record, run in self.repository.list_subagents(parent.id)
        ]
        return SessionSubagentsListResponse(parent_session_id=parent.id, items=items)

    def get(self, *, parent_session_id: str, child_session_id: str) -> SubagentSessionRead:
        self._require_main_parent(parent_session_id)
        row = self.repository.get_subagent(
            parent_session_id=parent_session_id,
            child_session_id=child_session_id,
        )
        if row is None:
            msg = "Subagent not found."
            raise ValueError(msg)
        session_record, run = row
        timeline_events = self._build_timeline_events(run)
        return self._serialize_subagent(
            session_record,
            run,
            timeline_events=timeline_events,
        )

    def list_messages(
        self,
        *,
        parent_session_id: str,
        child_session_id: str,
        limit: int | None = None,
        before_sequence: int | None = None,
    ):
        self._require_main_parent(parent_session_id)
        row = self.repository.get_subagent(
            parent_session_id=parent_session_id,
            child_session_id=child_session_id,
        )
        if row is None:
            msg = "Subagent not found."
            raise ValueError(msg)
        child, _ = row
        messages, has_more, next_before_sequence = self.repository.list_messages(
            child.id,
            limit=limit,
            before_sequence=before_sequence,
        )
        return (
            child,
            messages,
            has_more if limit is not None else None,
            next_before_sequence if limit is not None else None,
        )

    def cancel(
        self,
        *,
        parent_session_id: str,
        child_session_id: str,
    ) -> SubagentCancelResponse:
        parent = self._require_main_parent(parent_session_id)
        row = self.repository.get_subagent(
            parent_session_id=parent.id,
            child_session_id=child_session_id,
        )
        if row is None:
            msg = "Subagent not found."
            raise ValueError(msg)
        child, run = row
        goal_summary = self._goal_summary(child.delegated_goal or child.title)

        if run.lifecycle_status == "queued":
            summary = self.summary_builder.build(
                status="cancelled",
                goal=child.delegated_goal or child.title,
                task_run=self.repository.get_task_run(run.task_run_id),
                assistant_message=None,
                tool_calls=[],
                error_summary=None,
            )
            parent_payload = json.loads(summary.output_json)
            updated_run = self._run_with_sqlite_retry(
                lambda: self._finalize_run_immediate(
                    run_id=run.id,
                    status="cancelled",
                    final_summary=summary.summary_text,
                    final_output_json=summary.output_json,
                    estimated_cost_usd=None,
                    error_code="subagent_cancelled",
                    error_summary=summary.summary_text,
                    parent_message_text=self.summary_builder.parent_message_text(
                        child_title=child.title,
                        payload=parent_payload,
                    ),
                    terminal_event_type="subagent.cancelled",
                    terminal_event_payload=self._event_payload(
                        parent_session_id=parent.id,
                        child_session_id=child.id,
                        task_run_id=run.task_run_id,
                        goal_summary=goal_summary,
                        status="cancelled",
                    ),
                    terminal_event_summary="Subagent cancelled before execution.",
                )
            )
            self._commit_action(lambda: self._capture_terminal_memory(updated_run))
            return SubagentCancelResponse(
                parent_session_id=parent.id,
                child_session_id=child.id,
                lifecycle_status=updated_run.lifecycle_status,
                cancellation_requested_at=updated_run.cancellation_requested_at,
                finished_at=updated_run.finished_at,
            )

        if run.lifecycle_status == "running":
            updated_run = self._commit_action(lambda: self.repository.request_cancellation(run))
            self._commit_action(
                lambda: self.repository.record_audit_event(
                    agent_id=parent.agent_id,
                    event_type="subagent.cancel_requested",
                    entity_type="session_subagent_run",
                    entity_id=updated_run.id,
                    payload=self._event_payload(
                        parent_session_id=parent.id,
                        child_session_id=child.id,
                        task_run_id=updated_run.task_run_id,
                        goal_summary=goal_summary,
                        status=updated_run.lifecycle_status,
                        estimated_cost_usd=updated_run.estimated_cost_usd,
                    ),
                    summary_text="Subagent cancellation requested.",
                )
            )
            return SubagentCancelResponse(
                parent_session_id=parent.id,
                child_session_id=child.id,
                lifecycle_status=updated_run.lifecycle_status,
                cancellation_requested_at=updated_run.cancellation_requested_at,
                finished_at=updated_run.finished_at,
            )

        return SubagentCancelResponse(
            parent_session_id=parent.id,
            child_session_id=child.id,
            lifecycle_status=run.lifecycle_status,
            cancellation_requested_at=run.cancellation_requested_at,
            finished_at=run.finished_at,
        )

    def cleanup_stuck_runs(self) -> int:
        settings = get_settings()
        cleaned = 0
        running_runs = self._run_with_sqlite_retry(self.repository.list_running_subagents)
        for run, child, parent in running_runs:
            now = ensure_utc(utc_now())
            started_at = ensure_utc(run.started_at or run.updated_at or run.created_at)
            timeout_seconds = child.timeout_seconds or settings.subagent_run_timeout_seconds
            deadline = started_at + timedelta(
                seconds=timeout_seconds + settings.subagent_stuck_grace_seconds
            )
            if deadline > now:
                continue

            terminal_status = (
                "cancelled" if run.cancellation_requested_at is not None else "timed_out"
            )
            error_code = (
                "subagent_cancelled" if terminal_status == "cancelled" else "subagent_timed_out"
            )
            error_summary = (
                "Subagent execution was cancelled after exceeding its timeout window."
                if terminal_status == "cancelled"
                else "Subagent execution timed out before normal completion."
            )
            tool_calls = self.repository.list_tool_calls_for_task_run(run.task_run_id)
            summary = self.summary_builder.build(
                status=terminal_status,
                goal=child.delegated_goal or child.title,
                task_run=self.repository.get_task_run(run.task_run_id),
                assistant_message=None,
                tool_calls=tool_calls,
                error_summary=error_summary,
            )
            parent_payload = json.loads(summary.output_json)
            finalized_run = self._run_with_sqlite_retry(
                lambda: self._finalize_run_immediate(
                    run_id=run.id,
                    status=terminal_status,
                    final_summary=summary.summary_text,
                    final_output_json=summary.output_json,
                    estimated_cost_usd=self._coerce_float(parent_payload.get("estimated_cost_usd")),
                    error_code=error_code,
                    error_summary=error_summary,
                    parent_message_text=self.summary_builder.parent_message_text(
                        child_title=child.title,
                        payload=parent_payload,
                    ),
                    terminal_event_type=f"subagent.{terminal_status}",
                    terminal_event_payload=self._event_payload(
                        parent_session_id=parent.id,
                        child_session_id=child.id,
                        task_run_id=run.task_run_id,
                        goal_summary=self._goal_summary(child.delegated_goal or child.title),
                        status=terminal_status,
                        estimated_cost_usd=self._coerce_float(
                            parent_payload.get("estimated_cost_usd")
                        ),
                        extra={
                            "summary": str(parent_payload.get("summary") or summary.summary_text)
                        },
                    ),
                    terminal_event_summary=summary.summary_text,
                )
            )
            self._commit_action(lambda: self._capture_terminal_memory(finalized_run))
            cleaned += 1
        return cleaned

    def process_next_queued_run(self) -> bool:
        settings = get_settings()
        run = self._run_with_sqlite_retry(self._claim_next_queued_run_immediate)
        if run is None:
            return False

        sessions = self.repository.get_sessions([run.child_session_id, run.launcher_session_id])
        child = next((s for s in sessions if s.id == run.child_session_id), None)
        parent = next((s for s in sessions if s.id == run.launcher_session_id), None)

        if child is None or parent is None:
            msg = "Subagent run is missing its session lineage."
            raise ValueError(msg)

        goal_summary = self._goal_summary(child.delegated_goal or child.title)
        requested_toolsets = self._load_requested_toolsets(child.tool_profile)
        tool_permissions = self.execution_service.request_builder.list_active_tool_permissions(
            child.agent_id
        )
        resolution = resolve_subagent_tool_scope(
            requested_toolsets=requested_toolsets,
            tool_permissions=tool_permissions,
        )
        self._commit_action(
            lambda: self.repository.record_audit_event(
                agent_id=child.agent_id,
                event_type="subagent.tools.resolved",
                entity_type="session_subagent_run",
                entity_id=run.id,
                payload={
                    "toolsets": resolution.requested_toolsets,
                    "empty_groups": resolution.empty_groups,
                    "allowed_tool_names": resolution.allowed_tool_names,
                    "denied_tool_names": resolution.denied_tool_names,
                },
                summary_text="Subagent tool scope resolved.",
            )
        )

        def on_task_run_created(task, task_run) -> None:
            nonlocal run
            run = self._commit_action(
                lambda: self.repository.attach_execution_ids(
                    run,
                    task_id=task.id,
                    task_run_id=task_run.id,
                )
            )
            self._commit_action(
                lambda: self.repository.record_audit_event(
                    agent_id=child.agent_id,
                    event_type="subagent.started",
                    entity_type="session_subagent_run",
                    entity_id=run.id,
                    payload=self._event_payload(
                        parent_session_id=parent.id,
                        child_session_id=child.id,
                        task_run_id=task_run.id,
                        goal_summary=goal_summary,
                        status="running",
                    ),
                    summary_text="Subagent run started.",
                )
            )

        context_snapshot, parent_session_snapshot = self._split_persisted_context_snapshot(
            child.delegated_context_snapshot
        )
        outcome = self.execution_service.execute_delegated_session(
            session_id=child.id,
            goal=child.delegated_goal or child.title,
            context_snapshot=context_snapshot,
            allowed_tool_names=resolution.allowed_tool_names,
            model_override=child.model_override,
            max_iterations=child.max_iterations,
            parent_session_snapshot=parent_session_snapshot,
            timeout_seconds=child.timeout_seconds or settings.subagent_run_timeout_seconds,
            on_task_run_created=on_task_run_created,
            cancellation_probe=lambda: self.repository.should_cancel_run(run.id),
        )
        if run.task_run_id is None:
            run = self._commit_action(
                lambda: self.repository.attach_execution_ids(
                    run,
                    task_id=outcome.task.id,
                    task_run_id=outcome.task_run.id,
                )
            )

        current_run = self.repository.get_run(run.id)
        if current_run is None:
            msg = "Subagent run not found after execution."
            raise ValueError(msg)
        if current_run.lifecycle_status in {"completed", "failed", "cancelled", "timed_out"}:
            return True

        effective_status = (
            "cancelled" if current_run.cancellation_requested_at is not None else outcome.status
        )
        tool_calls = self.repository.list_tool_calls_for_task_run(current_run.task_run_id)
        summary = self.summary_builder.build(
            status=effective_status,
            goal=child.delegated_goal or child.title,
            task_run=outcome.task_run,
            assistant_message=outcome.assistant_message,
            tool_calls=tool_calls,
            error_summary=outcome.error_summary,
        )
        parent_payload = json.loads(summary.output_json)
        finalized_run = self._run_with_sqlite_retry(
            lambda: self._finalize_run_immediate(
                run_id=current_run.id,
                status=effective_status,
                final_summary=summary.summary_text,
                final_output_json=summary.output_json,
                estimated_cost_usd=outcome.task_run.estimated_cost_usd,
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
                parent_message_text=self.summary_builder.parent_message_text(
                    child_title=child.title,
                    payload=parent_payload,
                ),
                terminal_event_type={
                    "completed": "subagent.completed",
                    "failed": "subagent.failed",
                    "cancelled": "subagent.cancelled",
                    "timed_out": "subagent.timed_out",
                }.get(effective_status, "subagent.completed"),
                terminal_event_payload=self._event_payload(
                    parent_session_id=parent.id,
                    child_session_id=child.id,
                    task_run_id=current_run.task_run_id,
                    goal_summary=goal_summary,
                    status=effective_status,
                    estimated_cost_usd=outcome.task_run.estimated_cost_usd,
                    extra={"summary": str(parent_payload.get("summary") or summary.summary_text)},
                ),
                terminal_event_summary=summary.summary_text,
            )
        )
        self._commit_action(lambda: self._capture_terminal_memory(finalized_run))
        return finalized_run.lifecycle_status in KNOWN_SUBAGENT_STATUSES

    def aggregate_counts_for_sessions(
        self,
        session_ids: list[str],
    ) -> dict[str, SubagentCountsRead]:
        raw_counts = self.repository.aggregate_counts_by_launcher_session(session_ids)
        return {
            session_id: SubagentCountsRead(**counts) for session_id, counts in raw_counts.items()
        }

    def ensure_main_session_interaction_allowed(self, session_id: str) -> None:
        record = self.repository.get_session(session_id)
        if record is None:
            msg = "Session not found."
            raise ValueError(msg)
        if record.kind != "main":
            msg = "Subagent sessions cannot receive direct user interaction."
            raise ValueError(msg)

    def get_main_session(self, session_id: str):
        record = self.repository.get_session(session_id)
        if record is None or record.kind != "main":
            return None
        return record

    @staticmethod
    def _normalize_timeout_seconds(timeout_seconds: float | None) -> float:
        settings = get_settings()
        resolved = timeout_seconds or settings.subagent_run_timeout_seconds
        return min(resolved, settings.subagent_max_run_timeout_seconds)

    def _run_with_sqlite_retry(self, operation):
        for attempt in range(3):
            try:
                return operation()
            except OperationalError as exc:
                if not self._is_retryable_sqlite_error(exc) or attempt == 2:
                    raise
                self.session.rollback()
                time.sleep(0.05 * (attempt + 1))

    @staticmethod
    def _is_retryable_sqlite_error(exc: OperationalError) -> bool:
        message = str(exc).lower()
        return "database is locked" in message or "database is busy" in message

    def _commit_action(self, action: Callable[[], _T]) -> _T:
        try:
            result = action()
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def _run_immediate_repository_action(
        self,
        action: Callable[[SubagentRepository], _T],
    ) -> _T:
        bind = self.session.get_bind()
        if bind is None:
            msg = "Database bind is not available."
            raise RuntimeError(msg)
        with bind.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            with Session(bind=connection) as inner_session:
                repository = SubagentRepository(inner_session)
                try:
                    result = action(repository)
                    inner_session.commit()
                    connection.commit()
                except Exception:
                    inner_session.rollback()
                    connection.rollback()
                    raise
        self.session.expire_all()
        return result

    def _spawn_subagent_immediate(
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
        launcher_message_id: str | None,
        launcher_task_run_id: str | None,
    ) -> tuple[Any, Any, Any]:
        def _spawn(repository: SubagentRepository) -> tuple[str, str, str]:
            parent, child, run = repository.spawn_subagent(
                parent_session_id=parent_session_id,
                delegated_goal=delegated_goal,
                delegated_context_snapshot=delegated_context_snapshot,
                tool_profile=tool_profile,
                model_override=model_override,
                max_iterations=max_iterations,
                timeout_seconds=timeout_seconds,
                max_concurrency=max_concurrency,
                launcher_message_id=launcher_message_id,
                launcher_task_run_id=launcher_task_run_id,
            )
            return parent.id, child.id, run.id

        parent_id, child_id, run_id = self._run_immediate_repository_action(_spawn)
        parent = self.repository.get_session(parent_id)
        child = self.repository.get_session(child_id)
        run = self.repository.get_run(run_id)
        assert parent is not None
        assert child is not None
        assert run is not None
        return parent, child, run

    def _claim_next_queued_run_immediate(self):
        def _claim(repository: SubagentRepository):
            run = repository.claim_next_queued_run()
            return run.id if run is not None else None

        run_id = self._run_immediate_repository_action(_claim)
        if run_id is None:
            return None
        return self.repository.get_run(run_id)

    def _finalize_run_immediate(
        self,
        **kwargs,
    ):
        run_id = self._run_immediate_repository_action(
            lambda repository: repository.finalize_run(**kwargs).id
        )
        finalized_run = self.repository.get_run(run_id)
        assert finalized_run is not None
        return finalized_run

    def _require_main_parent(self, parent_session_id: str):
        record = self.repository.get_session(parent_session_id)
        if record is None:
            msg = "Session not found."
            raise ValueError(msg)
        if record.kind != "main":
            msg = "Only main sessions can access subagents."
            raise ValueError(msg)
        return record

    def _require_spawnable_parent(self, parent_session_id: str):
        record = self._require_main_parent(parent_session_id)
        if record.spawn_depth > 0:
            msg = "Subagent spawn depth cannot exceed 1."
            raise ValueError(msg)
        return record

    def _build_timeline_events(self, run) -> list[SubagentTimelineEventRead]:
        items: list[SubagentTimelineEventRead] = []
        for event in self.repository.list_subagent_audit_events(run=run):
            event_type = self._normalize_event_type(event.event_type)
            if event_type not in PUBLIC_SUBAGENT_EVENT_TYPES:
                continue
            payload = self._parse_json(event.payload_json)
            items.append(
                SubagentTimelineEventRead(
                    id=event.id,
                    event_type=event_type,
                    created_at=event.created_at,
                    status=self._coerce_status(payload.get("status")),
                    summary=self._timeline_summary(
                        event_type=event_type,
                        payload=payload,
                        fallback_summary=event.summary_text,
                    ),
                    task_run_id=self._coerce_string(payload.get("task_run_id")),
                    estimated_cost_usd=self._coerce_float(payload.get("estimated_cost_usd")),
                )
            )
        if run.lifecycle_status in {"completed", "failed", "cancelled", "timed_out"} and not any(
            item.event_type == f"subagent.{run.lifecycle_status}" for item in items
        ):
            items.append(
                SubagentTimelineEventRead(
                    id=f"synthetic:{run.id}:{run.lifecycle_status}",
                    event_type=f"subagent.{run.lifecycle_status}",
                    created_at=run.finished_at or run.updated_at,
                    status=run.lifecycle_status,
                    summary=run.final_summary
                    or run.error_summary
                    or f"Subagent {run.lifecycle_status}.",
                    task_run_id=run.task_run_id,
                    estimated_cost_usd=run.estimated_cost_usd,
                )
            )
        return items

    @staticmethod
    def _build_parent_snapshot(*, parent_title: str, messages) -> str:
        lines = [f"Parent session: {parent_title}"]
        for message in messages:
            excerpt = " ".join(message.content_text.split())[:180]
            lines.append(f"- {message.role}: {excerpt}")
        return "\n".join(lines)

    def _capture_terminal_memory(self, run: SessionSubagentRun) -> None:
        child = self.repository.get_session(run.child_session_id)
        if child is None:
            return
        output_text = run.final_summary or run.error_summary or ""
        if not output_text.strip():
            return
        task_run = self.repository.get_task_run(run.task_run_id)
        self.memory_capture.capture_execution_result(
            session_record=child,
            task_run=task_run,
            output_text=output_text,
        )

    @staticmethod
    def _build_context_snapshot(*, explicit_context: str | None, parent_snapshot: str) -> str:
        return (
            f"Explicit context:\n{(explicit_context or '(none)').strip() or '(none)'}\n\n"
            f"Parent snapshot:\n{parent_snapshot}"
        )

    @staticmethod
    def _split_persisted_context_snapshot(snapshot: str | None) -> tuple[str | None, str]:
        if snapshot is None:
            return None, ""

        marker = "\n\nParent snapshot:\n"
        prefix = "Explicit context:\n"
        if snapshot.startswith(prefix) and marker in snapshot:
            explicit_context, parent_snapshot = snapshot[len(prefix) :].split(marker, 1)
            return explicit_context, parent_snapshot

        return snapshot, ""

    @staticmethod
    def _load_requested_toolsets(tool_profile: str | None) -> list[str]:
        if not tool_profile:
            return []
        try:
            parsed = json.loads(tool_profile)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, str)]

    @staticmethod
    def _serialize_subagent(
        session_record,
        run,
        *,
        timeline_events: list[SubagentTimelineEventRead] | None = None,
    ) -> SubagentSessionRead:
        payload = SessionSubagentReadAdapter.from_records(
            session_record,
            run,
            timeline_events=timeline_events,
        )
        return SubagentSessionRead.model_validate(payload)

    @staticmethod
    def _goal_summary(goal: str) -> str:
        return " ".join(goal.split())[:160]

    def _resolve_launcher_message_id(
        self,
        *,
        parent_session_id: str,
        explicit_launcher_message_id: str | None,
    ) -> str | None:
        if explicit_launcher_message_id:
            message = self.repository.get_message(explicit_launcher_message_id)
            if message is None or message.session_id != parent_session_id:
                msg = "Launcher message must belong to the parent session."
                raise ValueError(msg)
            return message.id

        latest_parent_messages = self.repository.list_recent_messages(parent_session_id, limit=1)
        if not latest_parent_messages:
            return None
        return latest_parent_messages[-1].id

    @staticmethod
    def _event_payload(
        *,
        parent_session_id: str,
        child_session_id: str,
        goal_summary: str,
        status: str,
        task_run_id: str | None = None,
        estimated_cost_usd: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parent_session_id": parent_session_id,
            "child_session_id": child_session_id,
            "task_run_id": task_run_id,
            "goal_summary": goal_summary,
            "status": status,
            "estimated_cost_usd": estimated_cost_usd,
        }
        if extra:
            payload.update(extra)
        return payload

    @staticmethod
    def _normalize_event_type(event_type: str) -> str:
        return LEGACY_SUBAGENT_EVENT_TYPE_MAP.get(event_type, event_type)

    @staticmethod
    def _timeline_summary(
        *,
        event_type: str,
        payload: dict[str, Any],
        fallback_summary: str | None,
    ) -> str:
        explicit_summary = payload.get("summary")
        if isinstance(explicit_summary, str) and explicit_summary.strip():
            return explicit_summary.strip()
        goal_summary = payload.get("goal_summary")
        if event_type in {"subagent.spawned", "subagent.started"} and isinstance(
            goal_summary,
            str,
        ):
            return goal_summary
        if isinstance(fallback_summary, str) and fallback_summary.strip():
            return fallback_summary.strip()
        if isinstance(goal_summary, str) and goal_summary.strip():
            return goal_summary.strip()
        return event_type

    @staticmethod
    def _parse_json(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _coerce_status(value: Any) -> str | None:
        if isinstance(value, str) and value in KNOWN_SUBAGENT_STATUSES:
            return value
        return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _coerce_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None


class SessionSubagentReadAdapter:
    @staticmethod
    def from_records(
        session_record,
        run,
        *,
        timeline_events: list[SubagentTimelineEventRead] | None = None,
    ) -> dict[str, object]:
        return {
            "id": session_record.id,
            "agent_id": session_record.agent_id,
            "kind": session_record.kind,
            "parent_session_id": session_record.parent_session_id,
            "root_session_id": session_record.root_session_id,
            "spawn_depth": session_record.spawn_depth,
            "title": session_record.title,
            "summary": session_record.summary,
            "conversation_id": session_record.conversation_id,
            "status": session_record.status,
            "delegated_goal": session_record.delegated_goal,
            "delegated_context_snapshot": session_record.delegated_context_snapshot,
            "tool_profile": session_record.tool_profile,
            "model_override": session_record.model_override,
            "max_iterations": session_record.max_iterations,
            "timeout_seconds": session_record.timeout_seconds,
            "started_at": session_record.started_at,
            "last_message_at": session_record.last_message_at,
            "created_at": session_record.created_at,
            "updated_at": session_record.updated_at,
            "run": SubagentRunRead.model_validate(run),
            "timeline_events": timeline_events or [],
        }


SubagentService = SubagentDelegationService
