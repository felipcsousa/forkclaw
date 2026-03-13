from __future__ import annotations

from sqlmodel import Session

from app.kernel.contracts import (
    KernelExecutionRequest,
    KernelIdentity,
    KernelMemoryRecall,
    KernelMemoryRecallItem,
    KernelMessage,
    KernelRuntime,
    KernelSessionState,
    KernelSoul,
    KernelToolPolicy,
)
from app.models.entities import SessionRecord, Task, TaskRun, ToolPermission, utc_now
from app.repositories.agent_execution import AgentExecutionRepository
from app.services.memory import MemoryService
from app.services.operational_settings import OperationalSettingsService
from app.services.prompt_context_service import PromptContextService
from app.services.skills import SkillService


class ExecutionRequestBuilder:
    def __init__(
        self,
        session: Session,
        repository: AgentExecutionRepository | None = None,
    ):
        self.session = session
        self.repository = repository or AgentExecutionRepository(session)

    def build_simple(
        self,
        *,
        task: Task,
        task_run: TaskRun,
        session_record: SessionRecord,
        input_text: str,
        trigger_message_id: str | None,
    ) -> KernelExecutionRequest:
        return self._build_request(
            task=task,
            task_run=task_run,
            session_record=session_record,
            input_text=input_text,
            trigger_message_id=trigger_message_id,
        )

    def build_resume(
        self,
        *,
        task: Task,
        task_run: TaskRun,
        session_record: SessionRecord,
        trigger_message_id: str,
        input_text: str,
        history_cutoff_sequence: int,
    ) -> KernelExecutionRequest:
        return self._build_request(
            task=task,
            task_run=task_run,
            session_record=session_record,
            input_text=input_text,
            trigger_message_id=trigger_message_id,
            history_cutoff_sequence=history_cutoff_sequence,
        )

    def build_delegated(
        self,
        *,
        task: Task,
        task_run: TaskRun,
        session_record: SessionRecord,
        goal: str,
        context_snapshot: str | None,
        parent_session_snapshot: str,
        allowed_tool_permissions: list[ToolPermission],
        model_override: str | None,
        max_iterations_override: int | None,
    ) -> KernelExecutionRequest:
        return self._build_request(
            task=task,
            task_run=task_run,
            session_record=session_record,
            input_text=self.build_delegated_input(
                goal=goal,
                context_snapshot=context_snapshot,
                parent_session_snapshot=parent_session_snapshot,
            ),
            trigger_message_id=None,
            runtime_mode="delegated",
            tool_permissions_override=allowed_tool_permissions,
            model_override=model_override,
            max_iterations_override=max_iterations_override,
        )

    def list_active_tool_permissions(self, agent_id: str) -> list[ToolPermission]:
        return self.repository.list_tool_permissions(agent_id)

    def serialize_skill_resolution(
        self,
        request: KernelExecutionRequest,
    ) -> dict[str, object]:
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

    def serialize_memory_recall(
        self,
        request: KernelExecutionRequest,
    ) -> dict[str, object] | None:
        if request.memory_recall is None or not request.memory_recall.items:
            return None

        return {
            "reason_summary": request.memory_recall.reason_summary,
            "items": [
                {
                    "memory_id": item.memory_id,
                    "title": item.title,
                    "kind": item.kind,
                    "scope": item.scope,
                    "source_kind": item.source_kind,
                    "source_label": item.source_label,
                    "importance": item.importance,
                    "reason": item.reason,
                    "origin_session_id": item.origin_session_id,
                    "origin_subagent_session_id": item.origin_subagent_session_id,
                }
                for item in request.memory_recall.items
            ],
        }

    def _build_request(
        self,
        *,
        task: Task,
        task_run: TaskRun,
        session_record: SessionRecord,
        input_text: str,
        trigger_message_id: str | None,
        history_cutoff_sequence: int | None = None,
        runtime_mode: str = "simple",
        tool_permissions_override: list[ToolPermission] | None = None,
        model_override: str | None = None,
        max_iterations_override: int | None = None,
    ) -> KernelExecutionRequest:
        agent = self.repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        profile = self.repository.get_agent_profile(agent.id)
        if profile is None:
            msg = "Agent profile not found."
            raise ValueError(msg)

        runtime_config = OperationalSettingsService(self.session).resolve_runtime_config(profile)
        if history_cutoff_sequence is None:
            messages = self.repository.list_session_messages(
                session_record.id,
                conversation_id=session_record.conversation_id,
            )
        else:
            messages = self.repository.list_session_messages_until(
                session_record.id,
                history_cutoff_sequence,
                conversation_id=session_record.conversation_id,
            )
        settings = self.repository.list_settings()
        tool_permissions = (
            self.repository.list_tool_permissions(agent.id)
            if tool_permissions_override is None
            else tool_permissions_override
        )
        memory_service = MemoryService(self.session)
        recall_candidates = memory_service.select_for_recall(
            input_text=input_text,
            session_id=session_record.id,
        )
        resolved_input_text = memory_service.inject_recall_context(
            input_text=input_text,
            candidates=recall_candidates,
        )
        skill_bundle = SkillService(self.session).build_execution_bundle(
            tool_permissions=tool_permissions,
        )
        runtime_settings = {
            f"{setting.scope}.{setting.key}": setting.value_text or setting.value_json or ""
            for setting in settings
        }
        if max_iterations_override is not None:
            runtime_settings["runtime.max_iterations_per_execution"] = str(max_iterations_override)

        prompt_context_service = PromptContextService(self.session)
        summary_cutoff_sequence = history_cutoff_sequence
        if summary_cutoff_sequence is None and trigger_message_id is not None:
            trigger_message = self.repository.get_message(trigger_message_id)
            summary_cutoff_sequence = (
                trigger_message.sequence_number if trigger_message is not None else None
            )
        summary_memory = prompt_context_service.update_conversation_summary(
            agent_id=agent.id,
            session_record=session_record,
            cutoff_sequence=summary_cutoff_sequence,
            parent_session_id=session_record.parent_session_id,
        )
        if summary_memory is not None:
            self.repository.record_audit_event(
                agent_id=agent.id,
                event_type="conversation.summary.updated",
                entity_type="memory",
                entity_id=summary_memory.id,
                payload={
                    "session_id": session_record.id,
                    "conversation_id": session_record.conversation_id,
                },
                summary_text="Conversation summary updated.",
            )
        prompt_context = prompt_context_service.build_context(
            agent_id=agent.id,
            session_record=session_record,
            current_input=input_text,
        )
        self.repository.record_audit_event(
            agent_id=agent.id,
            event_type="prompt_context.resolved",
            entity_type="task_run",
            entity_id=task_run.id,
            payload=self._serialize_prompt_context(prompt_context),
            summary_text="Prompt context resolved.",
        )

        history_source = (
            messages[:-1]
            if (trigger_message_id is not None or history_cutoff_sequence is not None)
            else messages
        )
        history = [
            KernelMessage(
                message_id=item.id,
                role=item.role,
                content=item.content_text,
                sequence_number=item.sequence_number,
                created_at=item.created_at,
            )
            for item in history_source
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
                model_name=model_override or runtime_config.model_name,
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
                conversation_id=session_record.conversation_id,
                title=session_record.title,
                messages=history,
            ),
            runtime=KernelRuntime(
                mode=runtime_mode,
                task_id=task.id,
                task_run_id=task_run.id,
                trigger_message_id=trigger_message_id,
                skill_resolution=SkillService.to_kernel_skill_resolution(skill_bundle),
                settings=runtime_settings,
                started_at=utc_now(),
                environment_overlay=skill_bundle.environment_overlay,
            ),
            input_text=resolved_input_text,
            prompt_context=prompt_context,
            memory_recall=(
                KernelMemoryRecall(
                    reason_summary=f"{len(recall_candidates)} memory item(s) injected for recall.",
                    items=[
                        KernelMemoryRecallItem(
                            memory_id=candidate.item.id,
                            title=candidate.item.title,
                            kind=candidate.item.kind,
                            scope=candidate.item.scope,
                            source_kind=candidate.item.source_kind,
                            source_label=candidate.item.source_label,
                            importance=candidate.item.importance,
                            reason=candidate.reason,
                            origin_session_id=candidate.item.origin_session_id,
                            origin_subagent_session_id=candidate.item.origin_subagent_session_id,
                        )
                        for candidate in recall_candidates
                    ],
                )
                if recall_candidates
                else None
            ),
        )

    @staticmethod
    def _serialize_prompt_context(prompt_context) -> dict[str, object]:
        return {
            "layers": [
                {
                    "key": layer.key,
                    "budget_chars": layer.budget_chars,
                    "used_chars": layer.used_chars,
                }
                for layer in prompt_context.layers
            ],
            "included": [
                {
                    "memory_id": item.memory_id,
                    "namespace": item.namespace,
                    "memory_key": item.memory_key,
                    "layer": item.layer,
                    "reason": item.reason,
                }
                for item in prompt_context.included
            ],
            "excluded": [
                {
                    "memory_id": item.memory_id,
                    "namespace": item.namespace,
                    "memory_key": item.memory_key,
                    "layer": item.layer,
                    "reason": item.reason,
                }
                for item in prompt_context.excluded
            ],
        }

    @staticmethod
    def build_delegated_input(
        *,
        goal: str,
        context_snapshot: str | None,
        parent_session_snapshot: str,
    ) -> str:
        sections = [
            f"Delegated goal:\n{goal.strip()}",
            f"Explicit context:\n{(context_snapshot or '(none)').strip() or '(none)'}",
            f"Parent snapshot:\n{parent_session_snapshot.strip() or '(none)'}",
            (
                "Produce a concise, actionable result for the parent session. "
                "Do not request direct user interaction."
            ),
        ]
        return "\n\n".join(sections)
