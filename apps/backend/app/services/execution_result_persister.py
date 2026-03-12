from __future__ import annotations

import json
from dataclasses import dataclass
from math import ceil

from sqlmodel import Session

from app.kernel.contracts import KernelExecutionResult
from app.models.entities import Message, SessionRecord, Task, TaskRun
from app.repositories.agent_execution import AgentExecutionRepository


@dataclass(frozen=True)
class PersistedExecutionArtifacts:
    task_run: TaskRun
    assistant_message: Message | None


class ExecutionResultPersister:
    def __init__(
        self,
        session: Session,
        repository: AgentExecutionRepository | None = None,
    ):
        self.session = session
        self.repository = repository or AgentExecutionRepository(session)

    def record_skill_resolution(
        self,
        *,
        agent_id: str,
        task_run_id: str,
        payload: dict[str, object],
    ) -> None:
        self.repository.record_audit_event(
            agent_id=agent_id,
            event_type="skills.resolved",
            entity_type="task_run",
            entity_id=task_run_id,
            payload=payload,
            summary_text="Execution skills resolved.",
        )

    def append_assistant_message(
        self,
        *,
        session_record: SessionRecord,
        content: str,
    ) -> Message:
        message = self.repository.create_message(session_record.id, "assistant", content)
        self.repository.touch_session(session_record)
        return message

    def persist_result(
        self,
        *,
        agent_id: str,
        task: Task,
        task_run: TaskRun,
        session_record: SessionRecord,
        result: KernelExecutionResult,
        skill_resolution_payload: dict[str, object],
        assistant_message_text: str | None = None,
    ) -> PersistedExecutionArtifacts:
        assistant_message = (
            self.append_assistant_message(
                session_record=session_record,
                content=assistant_message_text,
            )
            if assistant_message_text
            else None
        )
        output_json = json.dumps(
            {
                "kernel_name": result.kernel_name,
                "model_name": result.model_name,
                "tools_used": result.tools_used,
                "skills": skill_resolution_payload,
                "raw_payload": result.raw_payload,
                "pending_approval_id": result.pending_approval_id,
                "pending_tool_call_id": result.pending_tool_call_id,
            },
            ensure_ascii=False,
        )
        estimated_cost_usd = self._extract_estimated_cost(result)
        if estimated_cost_usd is None:
            estimated_cost_usd = self._estimate_heuristic_cost(task, result.output_text)

        if result.status == "awaiting_approval":
            persisted = self.persist_task_state(
                agent_id=agent_id,
                task=task,
                task_run=task_run,
                session_id=session_record.id,
                status="awaiting_approval",
                output_json=output_json,
                error_message=None,
                estimated_cost_usd=estimated_cost_usd,
                event_type="kernel.execution.awaiting_approval",
                event_payload={
                    "session_id": session_record.id,
                    "task_id": task.id,
                    "approval_id": result.pending_approval_id,
                },
                event_level="warning",
                event_summary="Execution paused awaiting approval.",
            )
            return PersistedExecutionArtifacts(
                task_run=persisted,
                assistant_message=assistant_message,
            )

        if result.status == "failed":
            persisted = self.persist_task_state(
                agent_id=agent_id,
                task=task,
                task_run=task_run,
                session_id=session_record.id,
                status="failed",
                output_json=output_json,
                error_message=result.output_text,
                estimated_cost_usd=estimated_cost_usd,
                event_type="kernel.execution.failed",
                event_payload={"session_id": session_record.id, "task_id": task.id},
                event_level="error",
                event_summary="Execution finished with failure.",
            )
            return PersistedExecutionArtifacts(
                task_run=persisted,
                assistant_message=assistant_message,
            )

        persisted = self.persist_task_state(
            agent_id=agent_id,
            task=task,
            task_run=task_run,
            session_id=session_record.id,
            status="completed",
            output_json=output_json,
            error_message=None,
            estimated_cost_usd=estimated_cost_usd,
            event_type="kernel.execution.completed",
            event_payload={"session_id": session_record.id, "task_id": task.id},
            event_level="info",
            event_summary="Execution completed successfully.",
        )
        return PersistedExecutionArtifacts(task_run=persisted, assistant_message=assistant_message)

    def persist_task_state(
        self,
        *,
        agent_id: str,
        task: Task,
        task_run: TaskRun,
        session_id: str,
        status: str,
        output_json: str | None,
        error_message: str | None,
        estimated_cost_usd: float | None,
        event_type: str,
        event_payload: dict[str, object],
        event_summary: str,
        event_level: str = "info",
    ) -> TaskRun:
        if status == "awaiting_approval":
            self.repository.update_task_status(task, status=status)
            persisted_run = self.repository.update_task_run_status(
                task_run,
                status=status,
                output_json=output_json,
                error_message=error_message,
                estimated_cost_usd=estimated_cost_usd,
            )
        else:
            self.repository.complete_task(task, status=status)
            persisted_run = self.repository.complete_task_run(
                task_run,
                status=status,
                output_json=output_json,
                error_message=error_message,
                estimated_cost_usd=estimated_cost_usd,
            )

        self.repository.record_audit_event(
            agent_id=agent_id,
            event_type=event_type,
            entity_type="task_run",
            entity_id=task_run.id,
            payload={"session_id": session_id, "task_id": task.id, **event_payload},
            level=event_level,
            summary_text=event_summary,
        )
        return persisted_run

    @staticmethod
    def extract_estimated_cost(result: KernelExecutionResult) -> float | None:
        return ExecutionResultPersister._extract_estimated_cost(result)

    @staticmethod
    def _extract_estimated_cost(result: KernelExecutionResult) -> float | None:
        if not result.raw_payload:
            return None

        try:
            payload = json.loads(result.raw_payload)
        except json.JSONDecodeError:
            return None

        direct = payload.get("estimated_cost_usd")
        if isinstance(direct, (int, float)):
            return float(direct)

        usage = payload.get("usage")
        if isinstance(usage, dict):
            nested = usage.get("estimated_cost_usd")
            if isinstance(nested, (int, float)):
                return float(nested)

        return None

    @staticmethod
    def _estimate_heuristic_cost(task: Task, output_text: str) -> float:
        input_text = ""
        if task.payload_json:
            try:
                payload = json.loads(task.payload_json)
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                input_text = str(payload.get("message", "") or "")

        estimated_tokens = max(ceil((len(input_text) + len(output_text or "")) / 4), 1)
        return round(estimated_tokens * 0.000002, 6)
