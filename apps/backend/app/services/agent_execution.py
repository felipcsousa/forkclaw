from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session

from app.kernel.contracts import KernelExecutionRequest, KernelExecutionResult
from app.kernel.errors import KernelExecutionCancelledError
from app.kernel.factory import create_agent_kernel
from app.models.entities import Message, SessionRecord, Task, TaskRun
from app.repositories.agent_execution import AgentExecutionRepository
from app.schemas.execution import AgentExecutionResponse
from app.services.execution_request_builder import ExecutionRequestBuilder
from app.services.execution_result_persister import (
    ExecutionResultPersister,
    PersistedExecutionArtifacts,
)
from app.services.operational_settings import OperationalSettingsService
from app.services.tools import ToolService
from app.skills.runtime import runtime_env_overlay


@dataclass(frozen=True)
class DelegatedExecutionOutcome:
    task: Task
    task_run: TaskRun
    request: KernelExecutionRequest
    result: KernelExecutionResult | None
    assistant_message: Message | None
    status: str
    error_code: str | None = None
    error_summary: str | None = None


@dataclass(frozen=True)
class PreparedExecution:
    agent_id: str
    session_record: SessionRecord
    task: Task
    task_run: TaskRun
    request: KernelExecutionRequest
    user_message: Message | None = None


class AgentExecutionService:
    def __init__(self, session: Session):
        self.session = session
        self._repository = AgentExecutionRepository(session)
        self.request_builder = ExecutionRequestBuilder(
            session,
            repository=self._repository,
        )
        self.result_persister = ExecutionResultPersister(
            session,
            repository=self._repository,
        )

    def execute_simple(
        self,
        *,
        session_id: str | None,
        title: str | None,
        message: str,
    ) -> AgentExecutionResponse:
        prepared = self._commit_action(
            lambda: self._prepare_simple_execution(
                session_id=session_id,
                title=title,
                message=message,
            )
        )

        try:
            result = self._execute_request(prepared.request)
        except Exception as exc:
            error_message = str(exc)
            self._commit_action(
                lambda: self.result_persister.persist_task_state(
                    agent_id=prepared.agent_id,
                    task=prepared.task,
                    task_run=prepared.task_run,
                    session_id=prepared.session_record.id,
                    status="failed",
                    output_json=None,
                    error_message=error_message,
                    estimated_cost_usd=None,
                    event_type="kernel.execution.failed",
                    event_payload={
                        "session_id": prepared.session_record.id,
                        "task_id": prepared.task.id,
                        "error": error_message,
                    },
                    event_level="error",
                    event_summary="Agent execution failed.",
                )
            )
            raise

        persisted = self._commit_action(
            lambda: self.result_persister.persist_result(
                agent_id=prepared.agent_id,
                task=prepared.task,
                task_run=prepared.task_run,
                session_record=prepared.session_record,
                result=result,
                skill_resolution_payload=self.request_builder.serialize_skill_resolution(
                    prepared.request
                ),
                assistant_message_text=result.output_text,
            )
        )
        return AgentExecutionResponse(
            task_id=prepared.task.id,
            task_run_id=persisted.task_run.id,
            session_id=prepared.session_record.id,
            user_message_id=prepared.user_message.id if prepared.user_message else None,
            assistant_message_id=persisted.assistant_message.id
            if persisted.assistant_message
            else None,
            status=persisted.task_run.status,
            output_text=result.output_text,
            kernel_name=result.kernel_name,
            model_name=result.model_name,
            tools_used=result.tools_used,
            finished_at=persisted.task_run.finished_at,
        )

    def build_resume_request(
        self,
        *,
        task: Task,
        task_run: TaskRun,
        session_id: str,
        trigger_message_id: str,
        input_text: str,
        history_cutoff_sequence: int,
    ) -> KernelExecutionRequest:
        session_record = self._require_session(session_id)
        return self.request_builder.build_resume(
            task=task,
            task_run=task_run,
            session_record=session_record,
            trigger_message_id=trigger_message_id,
            input_text=input_text,
            history_cutoff_sequence=history_cutoff_sequence,
        )

    def execute_delegated_session(
        self,
        *,
        session_id: str,
        goal: str,
        context_snapshot: str | None,
        allowed_tool_names: list[str],
        model_override: str | None,
        max_iterations: int | None,
        parent_session_snapshot: str,
        timeout_seconds: float,
        on_task_run_created: Callable[[Task, TaskRun], None] | None = None,
        cancellation_probe: Callable[[], bool] | None = None,
    ) -> DelegatedExecutionOutcome:
        prepared = self._commit_action(
            lambda: self._prepare_delegated_execution(
                session_id=session_id,
                goal=goal,
                context_snapshot=context_snapshot,
                allowed_tool_names=allowed_tool_names,
                model_override=model_override,
                max_iterations=max_iterations,
                parent_session_snapshot=parent_session_snapshot,
            )
        )
        if on_task_run_created is not None:
            on_task_run_created(prepared.task, prepared.task_run)

        try:
            self._raise_if_cancelled(cancellation_probe)
            result = self._execute_request(
                prepared.request,
                timeout_seconds=timeout_seconds,
                cancellation_probe=cancellation_probe,
            )
        except KernelExecutionCancelledError:
            return self._persist_terminal_outcome(
                prepared=prepared,
                request=prepared.request,
                status="cancelled",
                error_code="subagent_cancelled",
                error_summary="Subagent execution was cancelled before normal completion.",
                event_type="kernel.execution.cancelled",
                event_level="warning",
                event_summary="Subagent execution cancelled.",
            )
        except TimeoutError:
            return self._persist_terminal_outcome(
                prepared=prepared,
                request=prepared.request,
                status="timed_out",
                error_code="subagent_timed_out",
                error_summary="Subagent execution timed out before normal completion.",
                event_type="kernel.execution.timed_out",
                event_level="warning",
                event_summary="Subagent execution timed out.",
            )
        except Exception:
            return self._persist_terminal_outcome(
                prepared=prepared,
                request=prepared.request,
                status="failed",
                error_code="subagent_execution_failed",
                error_summary="Subagent execution failed before producing a result.",
                event_type="kernel.execution.failed",
                event_level="error",
                event_summary="Subagent execution failed.",
            )

        normalized_result, error_code, error_summary = self._normalize_subagent_result(result)
        try:
            self._raise_if_cancelled(cancellation_probe)
        except KernelExecutionCancelledError:
            return self._persist_terminal_outcome(
                prepared=prepared,
                request=prepared.request,
                status="cancelled",
                error_code="subagent_cancelled",
                error_summary="Subagent execution was cancelled before normal completion.",
                event_type="kernel.execution.cancelled",
                event_level="warning",
                event_summary="Subagent execution cancelled.",
            )

        persisted = self._commit_action(
            lambda: self.result_persister.persist_result(
                agent_id=prepared.agent_id,
                task=prepared.task,
                task_run=prepared.task_run,
                session_record=prepared.session_record,
                result=normalized_result,
                skill_resolution_payload=self.request_builder.serialize_skill_resolution(
                    prepared.request
                ),
                assistant_message_text=normalized_result.output_text,
            )
        )
        return DelegatedExecutionOutcome(
            task=prepared.task,
            task_run=persisted.task_run,
            request=prepared.request,
            result=normalized_result,
            assistant_message=persisted.assistant_message,
            status=persisted.task_run.status,
            error_code=error_code,
            error_summary=error_summary,
        )

    def persist_execution_result(
        self,
        *,
        agent_id: str,
        task: Task,
        task_run: TaskRun,
        session_id: str,
        request: KernelExecutionRequest,
        result: KernelExecutionResult,
        assistant_message_text: str | None = None,
    ) -> PersistedExecutionArtifacts:
        session_record = self._require_session(session_id)
        return self._commit_action(
            lambda: self.result_persister.persist_result(
                agent_id=agent_id,
                task=task,
                task_run=task_run,
                session_record=session_record,
                result=result,
                skill_resolution_payload=self.request_builder.serialize_skill_resolution(request),
                assistant_message_text=assistant_message_text,
            )
        )

    def append_assistant_message(
        self,
        *,
        session_id: str,
        content: str,
    ) -> Message:
        session_record = self._require_session(session_id)
        return self._commit_action(
            lambda: self.result_persister.append_assistant_message(
                session_record=session_record,
                content=content,
            )
        )

    def persist_terminal_status(
        self,
        *,
        agent_id: str,
        task: Task,
        task_run: TaskRun,
        session_id: str,
        status: str,
        error_message: str | None,
        output_json: str | None,
        estimated_cost_usd: float | None,
        event_type: str,
        event_level: str,
        event_summary: str,
        event_payload: dict[str, object] | None = None,
        assistant_message_text: str | None = None,
    ) -> PersistedExecutionArtifacts:
        session_record = self._require_session(session_id)

        def _persist() -> PersistedExecutionArtifacts:
            assistant_message = None
            if assistant_message_text:
                assistant_message = self.result_persister.append_assistant_message(
                    session_record=session_record,
                    content=assistant_message_text,
                )
            persisted_run = self.result_persister.persist_task_state(
                agent_id=agent_id,
                task=task,
                task_run=task_run,
                session_id=session_id,
                status=status,
                output_json=output_json,
                error_message=error_message,
                estimated_cost_usd=estimated_cost_usd,
                event_type=event_type,
                event_payload=event_payload or {},
                event_level=event_level,
                event_summary=event_summary,
            )
            return PersistedExecutionArtifacts(
                task_run=persisted_run,
                assistant_message=assistant_message,
            )

        return self._commit_action(_persist)

    def record_skill_resolution(
        self,
        *,
        agent_id: str,
        task_run_id: str,
        request: KernelExecutionRequest,
    ) -> None:
        self._commit_action(
            lambda: self.result_persister.record_skill_resolution(
                agent_id=agent_id,
                task_run_id=task_run_id,
                payload=self.request_builder.serialize_skill_resolution(request),
            )
        )

    def _prepare_simple_execution(
        self,
        *,
        session_id: str | None,
        title: str | None,
        message: str,
    ) -> PreparedExecution:
        agent = self._require_default_agent()
        OperationalSettingsService(self.session).enforce_budget_limits(input_text=message)
        session_record = (
            self._require_session(session_id)
            if session_id
            else self._repository.create_main_session(agent_id=agent.id, title=title)
        )
        user_message = self._repository.create_message(session_record.id, "user", message)
        self._repository.touch_session(session_record)
        task = self._repository.create_task(
            agent.id,
            session_record.id,
            {"message": message, "user_message_id": user_message.id},
        )
        task_run = self._repository.create_task_run(task.id)
        self._repository.record_audit_event(
            agent_id=agent.id,
            event_type="kernel.execution.started",
            entity_type="task_run",
            entity_id=task_run.id,
            payload={"session_id": session_record.id, "task_id": task.id},
            summary_text="Agent execution started.",
        )
        request = self.request_builder.build_simple(
            task=task,
            task_run=task_run,
            session_record=session_record,
            input_text=message,
            trigger_message_id=user_message.id,
        )
        self.result_persister.record_skill_resolution(
            agent_id=agent.id,
            task_run_id=task_run.id,
            payload=self.request_builder.serialize_skill_resolution(request),
        )
        return PreparedExecution(
            agent_id=agent.id,
            session_record=session_record,
            task=task,
            task_run=task_run,
            request=request,
            user_message=user_message,
        )

    def _prepare_delegated_execution(
        self,
        *,
        session_id: str,
        goal: str,
        context_snapshot: str | None,
        allowed_tool_names: list[str],
        model_override: str | None,
        max_iterations: int | None,
        parent_session_snapshot: str,
    ) -> PreparedExecution:
        agent = self._require_default_agent()
        session_record = self._require_session(session_id)
        input_text = self.request_builder.build_delegated_input(
            goal=goal,
            context_snapshot=context_snapshot,
            parent_session_snapshot=parent_session_snapshot,
        )
        OperationalSettingsService(self.session).enforce_budget_limits(input_text=input_text)
        task = self._repository.create_task(
            agent.id,
            session_record.id,
            {
                "goal": goal,
                "context_snapshot": context_snapshot,
                "parent_session_snapshot": parent_session_snapshot,
                "allowed_tool_names": allowed_tool_names,
            },
            title="Subagent delegated execution",
            kind="subagent_execution",
        )
        task_run = self._repository.create_task_run(task.id)
        self._repository.record_audit_event(
            agent_id=agent.id,
            event_type="kernel.execution.started",
            entity_type="task_run",
            entity_id=task_run.id,
            payload={"session_id": session_record.id, "task_id": task.id},
            summary_text="Subagent execution started.",
        )
        tool_permissions = [
            permission
            for permission in self.request_builder.list_active_tool_permissions(agent.id)
            if permission.tool_name in allowed_tool_names
        ]
        request = self.request_builder.build_delegated(
            task=task,
            task_run=task_run,
            session_record=session_record,
            goal=goal,
            context_snapshot=context_snapshot,
            parent_session_snapshot=parent_session_snapshot,
            allowed_tool_permissions=tool_permissions,
            model_override=model_override,
            max_iterations_override=max_iterations,
        )
        self.result_persister.record_skill_resolution(
            agent_id=agent.id,
            task_run_id=task_run.id,
            payload=self.request_builder.serialize_skill_resolution(request),
        )
        return PreparedExecution(
            agent_id=agent.id,
            session_record=session_record,
            task=task,
            task_run=task_run,
            request=request,
        )

    def _persist_terminal_outcome(
        self,
        *,
        prepared: PreparedExecution,
        request: KernelExecutionRequest,
        status: str,
        error_code: str,
        error_summary: str,
        event_type: str,
        event_level: str,
        event_summary: str,
    ) -> DelegatedExecutionOutcome:
        persisted = self.persist_terminal_status(
            agent_id=prepared.agent_id,
            task=prepared.task,
            task_run=prepared.task_run,
            session_id=prepared.session_record.id,
            status=status,
            error_message=error_summary,
            output_json=None,
            estimated_cost_usd=None,
            event_type=event_type,
            event_level=event_level,
            event_summary=event_summary,
            event_payload={},
        )
        return DelegatedExecutionOutcome(
            task=prepared.task,
            task_run=persisted.task_run,
            request=request,
            result=None,
            assistant_message=persisted.assistant_message,
            status=status,
            error_code=error_code,
            error_summary=error_summary,
        )

    def _execute_request(
        self,
        request: KernelExecutionRequest,
        *,
        timeout_seconds: float | None = None,
        cancellation_probe: Callable[[], bool] | None = None,
    ) -> KernelExecutionResult:
        tool_service = ToolService(self.session)

        async def _run() -> KernelExecutionResult:
            kernel = create_agent_kernel(
                tool_executor=tool_service,
                cancellation_probe=cancellation_probe,
            )
            if timeout_seconds is None:
                return await kernel.execute(request)
            return await asyncio.wait_for(kernel.execute(request), timeout=timeout_seconds)

        with runtime_env_overlay(request.runtime.environment_overlay):
            return asyncio.run(_run())

    @staticmethod
    def _raise_if_cancelled(cancellation_probe: Callable[[], bool] | None) -> None:
        if cancellation_probe is None:
            return
        if cancellation_probe():
            msg = "Subagent execution was cancelled."
            raise KernelExecutionCancelledError(msg)

    @staticmethod
    def _normalize_subagent_result(
        result: KernelExecutionResult,
    ) -> tuple[KernelExecutionResult, str | None, str | None]:
        if result.status == "awaiting_approval":
            summary = "Subagent execution stopped because a tool requires approval."
            return (
                KernelExecutionResult(
                    status="failed",
                    output_text=summary,
                    finish_reason=result.finish_reason,
                    kernel_name=result.kernel_name,
                    model_name=result.model_name,
                    tools_used=result.tools_used,
                    raw_payload=result.raw_payload,
                ),
                "subagent_approval_required",
                summary,
            )
        if result.status == "failed":
            return result, "subagent_execution_failed", result.output_text
        return result, None, None

    def _require_default_agent(self):
        agent = self._repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)
        profile = self._repository.get_agent_profile(agent.id)
        if profile is None:
            msg = "Agent profile not found."
            raise ValueError(msg)
        return agent

    def _require_session(self, session_id: str | None) -> SessionRecord:
        if not session_id:
            msg = "Session not found."
            raise ValueError(msg)
        session_record = self._repository.get_session(session_id)
        if session_record is None:
            msg = "Session not found."
            raise ValueError(msg)
        return session_record

    def _commit_action(self, action):
        try:
            result = action()
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise
