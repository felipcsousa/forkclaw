from __future__ import annotations

import asyncio
import json
from math import ceil

from sqlmodel import Session

from app.kernel.contracts import (
    KernelExecutionRequest,
    KernelExecutionResult,
    KernelIdentity,
    KernelMessage,
    KernelRuntime,
    KernelSessionState,
    KernelSoul,
    KernelToolPolicy,
)
from app.kernel.factory import create_agent_kernel
from app.models.entities import Task, TaskRun, utc_now
from app.repositories.agent_execution import AgentExecutionRepository
from app.schemas.execution import AgentExecutionResponse
from app.services.operational_settings import OperationalSettingsService
from app.services.skills import SkillService
from app.services.tools import ToolService
from app.skills.runtime import runtime_env_overlay


class AgentExecutionService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = AgentExecutionRepository(session)

    def execute_simple(
        self,
        *,
        session_id: str | None,
        title: str | None,
        message: str,
    ) -> AgentExecutionResponse:
        agent = self.repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        profile = self.repository.get_agent_profile(agent.id)
        if profile is None:
            msg = "Agent profile not found."
            raise ValueError(msg)

        operational_settings = OperationalSettingsService(self.session)
        operational_settings.enforce_budget_limits(input_text=message)
        session_record = self.repository.get_or_create_session(agent.id, session_id, title)
        user_message = self.repository.create_message(session_record.id, "user", message)
        self.repository.touch_session(session_record)
        task = self.repository.create_task(
            agent.id,
            session_record.id,
            {"message": message, "user_message_id": user_message.id},
        )
        task_run = self.repository.create_task_run(task.id)

        self.repository.record_audit_event(
            agent_id=agent.id,
            event_type="kernel.execution.started",
            entity_type="task_run",
            entity_id=task_run.id,
            payload={"session_id": session_record.id, "task_id": task.id},
            summary_text="Agent execution started.",
        )

        try:
            request = self._build_request(
                task=task,
                task_run=task_run,
                session_id=session_record.id,
                input_text=message,
                trigger_message_id=user_message.id,
            )
            self.record_skill_resolution(
                agent_id=agent.id,
                task_run_id=task_run.id,
                request=request,
            )
            tool_service = ToolService(self.session)
            with runtime_env_overlay(request.runtime.environment_overlay):
                result = asyncio.run(
                    create_agent_kernel(tool_executor=tool_service).execute(request)
                )
            assistant_message = self.repository.create_message(
                session_record.id,
                "assistant",
                result.output_text,
            )
            self.repository.touch_session(session_record)
            completed_run = self._persist_execution_result(
                agent_id=agent.id,
                task=task,
                task_run=task_run,
                session_id=session_record.id,
                request=request,
                result=result,
            )
            return AgentExecutionResponse(
                task_id=task.id,
                task_run_id=completed_run.id,
                session_id=session_record.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                status=completed_run.status,
                output_text=result.output_text,
                kernel_name=result.kernel_name,
                model_name=result.model_name,
                tools_used=result.tools_used,
                finished_at=completed_run.finished_at,
            )
        except Exception as exc:
            self.repository.complete_task(task, status="failed")
            self.repository.complete_task_run(
                task_run,
                status="failed",
                output_json=None,
                error_message=str(exc),
            )
            self.repository.record_audit_event(
                agent_id=agent.id,
                event_type="kernel.execution.failed",
                entity_type="task_run",
                entity_id=task_run.id,
                payload={"session_id": session_record.id, "task_id": task.id, "error": str(exc)},
                level="error",
                summary_text="Agent execution failed.",
            )
            raise

    def _build_request(
        self,
        *,
        task: Task,
        task_run: TaskRun,
        session_id: str,
        input_text: str,
        trigger_message_id: str | None,
        history_cutoff_sequence: int | None = None,
    ) -> KernelExecutionRequest:
        agent = self.repository.get_default_agent()
        assert agent is not None

        profile = self.repository.get_agent_profile(agent.id)
        assert profile is not None
        operational_settings = OperationalSettingsService(self.session)
        runtime_config = operational_settings.resolve_runtime_config(profile)

        session_record = self.repository.get_or_create_session(agent.id, session_id, None)
        if history_cutoff_sequence is None:
            messages = self.repository.list_session_messages(session_id)
        else:
            messages = self.repository.list_session_messages_until(
                session_id,
                history_cutoff_sequence,
            )
        settings = self.repository.list_settings()
        tool_permissions = self.repository.list_tool_permissions(agent.id)
        skill_bundle = SkillService(self.session).build_execution_bundle(
            tool_permissions=tool_permissions,
        )

        history = [
            KernelMessage(
                message_id=item.id,
                role=item.role,
                content=item.content_text,
                sequence_number=item.sequence_number,
                created_at=item.created_at,
            )
            for item in messages[:-1]
        ]

        return KernelExecutionRequest(
            identity=KernelIdentity(
                agent_id=agent.id,
                slug=agent.slug,
                name=agent.name,
                description=agent.description,
                identity_text=profile.identity_text,
            ),
            soul=KernelSoul(
                soul_text=profile.soul_text,
                user_context_text=profile.user_context_text,
                policy_base_text=profile.policy_base_text,
                model_provider=runtime_config.provider,
                model_name=runtime_config.model_name,
            ),
            skills=skill_bundle.skills,
            tools=[
                KernelToolPolicy(
                    tool_name=permission.tool_name,
                    permission_level=permission.permission_level,
                    approval_required=permission.approval_required,
                    workspace_path=permission.workspace_path,
                )
                for permission in tool_permissions
            ],
            session=KernelSessionState(
                session_id=session_record.id,
                title=session_record.title,
                messages=history,
            ),
            runtime=KernelRuntime(
                mode="simple",
                task_id=task.id,
                task_run_id=task_run.id,
                trigger_message_id=trigger_message_id,
                skill_resolution=SkillService.to_kernel_skill_resolution(skill_bundle),
                settings={
                    f"{setting.scope}.{setting.key}": setting.value_text or setting.value_json or ""
                    for setting in settings
                },
                started_at=utc_now(),
                environment_overlay=skill_bundle.environment_overlay,
            ),
            input_text=input_text,
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
        return self._build_request(
            task=task,
            task_run=task_run,
            session_id=session_id,
            input_text=input_text,
            trigger_message_id=trigger_message_id,
            history_cutoff_sequence=history_cutoff_sequence,
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
    ) -> TaskRun:
        return self._persist_execution_result(
            agent_id=agent_id,
            task=task,
            task_run=task_run,
            session_id=session_id,
            request=request,
            result=result,
        )

    def _persist_execution_result(
        self,
        *,
        agent_id: str,
        task: Task,
        task_run: TaskRun,
        session_id: str,
        request: KernelExecutionRequest,
        result: KernelExecutionResult,
    ) -> TaskRun:
        output_json = json.dumps(
            {
                "kernel_name": result.kernel_name,
                "model_name": result.model_name,
                "tools_used": result.tools_used,
                "skills": self._serialize_skill_resolution(request),
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
            self.repository.update_task_status(task, status="awaiting_approval")
            paused_run = self.repository.update_task_run_status(
                task_run,
                status="awaiting_approval",
                output_json=output_json,
                estimated_cost_usd=estimated_cost_usd,
            )
            self.repository.record_audit_event(
                agent_id=agent_id,
                event_type="kernel.execution.awaiting_approval",
                entity_type="task_run",
                entity_id=task_run.id,
                payload={
                    "session_id": session_id,
                    "task_id": task.id,
                    "approval_id": result.pending_approval_id,
                },
                level="warning",
                summary_text="Execution paused awaiting approval.",
            )
            return paused_run

        if result.status == "failed":
            self.repository.complete_task(task, status="failed")
            failed_run = self.repository.complete_task_run(
                task_run,
                status="failed",
                output_json=output_json,
                error_message=result.output_text,
                estimated_cost_usd=estimated_cost_usd,
            )
            self.repository.record_audit_event(
                agent_id=agent_id,
                event_type="kernel.execution.failed",
                entity_type="task_run",
                entity_id=task_run.id,
                payload={"session_id": session_id, "task_id": task.id},
                level="error",
                summary_text="Execution finished with failure.",
            )
            return failed_run

        self.repository.complete_task(task, status="completed")
        completed_run = self.repository.complete_task_run(
            task_run,
            status="completed",
            output_json=output_json,
            estimated_cost_usd=estimated_cost_usd,
        )
        self.repository.record_audit_event(
            agent_id=agent_id,
            event_type="kernel.execution.completed",
            entity_type="task_run",
            entity_id=task_run.id,
            payload={"session_id": session_id, "task_id": task.id},
            summary_text="Execution completed successfully.",
        )
        return completed_run

    def record_skill_resolution(
        self,
        *,
        agent_id: str,
        task_run_id: str,
        request: KernelExecutionRequest,
    ) -> None:
        self.repository.record_audit_event(
            agent_id=agent_id,
            event_type="skills.resolved",
            entity_type="task_run",
            entity_id=task_run_id,
            payload=self._serialize_skill_resolution(request),
            summary_text="Execution skills resolved.",
        )

    @staticmethod
    def _serialize_skill_resolution(request: KernelExecutionRequest) -> dict[str, object]:
        return {
            "strategy": request.runtime.skill_resolution.strategy,
            "items": [
                {
                    "key": item.key,
                    "name": item.name,
                    "origin": item.origin,
                    "source_path": item.source_path,
                    "selected": item.selected,
                    "eligible": item.eligible,
                    "blocked_reasons": item.blocked_reasons,
                }
                for item in request.runtime.skill_resolution.items
            ],
        }

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
