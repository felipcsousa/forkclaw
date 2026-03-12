from __future__ import annotations

import json

from sqlmodel import Session

from app.kernel.contracts import KernelExecutionResult
from app.kernel.factory import create_agent_kernel
from app.repositories.agent_profile import AgentProfileRepository
from app.repositories.approvals import ApprovalBundle, ApprovalRepository
from app.repositories.tools import ToolingRepository
from app.schemas.approval import ApprovalActionResponse, ApprovalRead
from app.services.agent_execution import AgentExecutionService
from app.services.tools import ToolService
from app.skills.runtime import runtime_env_overlay


class ApprovalService:
    def __init__(self, session: Session):
        self.session = session
        self.approvals = ApprovalRepository(session)
        self.agent_repository = AgentProfileRepository(session)
        self.tool_repository = ToolingRepository(session)
        self.execution_service = AgentExecutionService(session)
        self.tool_service = ToolService(session)

    def list_approvals(self) -> list[ApprovalRead]:
        agent = self.agent_repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        items = []
        for approval in self.approvals.list_approvals(agent.id):
            bundle = self.approvals.get_bundle(approval.id)
            if bundle is None:
                continue
            items.append(self._serialize_bundle(bundle))
        return items

    def get_approval(self, approval_id: str) -> ApprovalRead:
        bundle = self.approvals.get_bundle(approval_id)
        if bundle is None:
            msg = "Approval not found."
            raise ValueError(msg)
        return self._serialize_bundle(bundle)

    def approve(self, approval_id: str) -> ApprovalActionResponse:
        bundle = self._require_pending_bundle(approval_id)
        if bundle.tool_call is None or bundle.task is None or bundle.task_run is None:
            msg = "Approval is missing execution context."
            raise ValueError(msg)

        approval = self.approvals.update_approval(bundle.approval, status="approved")
        self.tool_repository.record_audit_event(
            agent_id=approval.agent_id,
            event_type="approval.approved",
            entity_type="approval",
            entity_id=approval.id,
            payload={"tool_call_id": approval.tool_call_id or ""},
        )

        message = self.approvals.get_message(bundle.tool_call.message_id)
        if message is None:
            msg = "Trigger message not found."
            raise ValueError(msg)
        if bundle.session is None:
            msg = "Session not found."
            raise ValueError(msg)

        request = self.execution_service.build_resume_request(
            task=bundle.task,
            task_run=bundle.task_run,
            session_id=bundle.session.id,
            trigger_message_id=message.id,
            input_text=message.content_text,
            history_cutoff_sequence=message.sequence_number,
        )
        self.execution_service.record_skill_resolution(
            agent_id=approval.agent_id,
            task_run_id=bundle.task_run.id,
            request=request,
        )

        with runtime_env_overlay(request.runtime.environment_overlay):
            tool_outcome = self.tool_service.continue_approved_tool_call(
                request=request,
                tool_call_id=bundle.tool_call.id,
            )

            if tool_outcome.status == "failed":
                result = KernelExecutionResult(
                    status="failed",
                    output_text=tool_outcome.output_text,
                    finish_reason="tool_error",
                    kernel_name="nanobot",
                    model_name=request.soul.model_name,
                    tools_used=[bundle.tool_call.tool_name],
                    raw_payload=json.dumps(
                        {
                            "tool_name": bundle.tool_call.tool_name,
                            "tool_call_id": bundle.tool_call.id,
                            "tool_status": tool_outcome.status,
                            "error_message": tool_outcome.error_message,
                        },
                        ensure_ascii=False,
                    ),
                )
            else:
                tool_arguments = {}
                if bundle.tool_call.input_json:
                    try:
                        parsed_arguments = json.loads(bundle.tool_call.input_json)
                    except json.JSONDecodeError:
                        parsed_arguments = {}
                    if isinstance(parsed_arguments, dict):
                        tool_arguments = parsed_arguments
                result = self._resume_kernel(
                    request=request,
                    tool_name=bundle.tool_call.tool_name,
                    tool_call_id=bundle.tool_call.id,
                    tool_arguments=tool_arguments,
                    tool_output=tool_outcome.output_text,
                )

        persisted = self.execution_service.persist_execution_result(
            agent_id=approval.agent_id,
            task=bundle.task,
            task_run=bundle.task_run,
            session_id=bundle.session.id,
            request=request,
            result=result,
            assistant_message_text=result.output_text,
            record_message_completed_event=bundle.task.kind == "agent_execution_async",
        )

        refreshed_bundle = self.approvals.get_bundle(approval.id)
        assert refreshed_bundle is not None
        assert refreshed_bundle.tool_call is not None

        return ApprovalActionResponse(
            approval=self._serialize_bundle(refreshed_bundle),
            task_run_status=persisted.task_run.status,
            tool_call_status=refreshed_bundle.tool_call.status,
            output_text=result.output_text,
            assistant_message_id=persisted.assistant_message.id
            if persisted.assistant_message is not None
            else None,
        )

    def deny(self, approval_id: str) -> ApprovalActionResponse:
        bundle = self._require_pending_bundle(approval_id)
        if bundle.tool_call is None or bundle.task is None or bundle.task_run is None:
            msg = "Approval is missing execution context."
            raise ValueError(msg)
        if bundle.session is None:
            msg = "Session not found."
            raise ValueError(msg)

        approval = self.approvals.update_approval(bundle.approval, status="denied")
        self.tool_repository.update_tool_call(
            bundle.tool_call,
            status="denied",
            output_payload={"message": "Approval denied by user."},
        )
        persisted = self.execution_service.persist_terminal_status(
            agent_id=approval.agent_id,
            task=bundle.task,
            task_run=bundle.task_run,
            session_id=bundle.session.id,
            status="failed",
            error_message="Approval denied by user.",
            output_json=None,
            estimated_cost_usd=None,
            event_type="kernel.execution.failed",
            event_level="error",
            event_summary="Execution finished with failure.",
            event_payload={},
            assistant_message_text=(
                f"Approval denied for `{bundle.tool_call.tool_name}`. "
                "The action was not executed."
            ),
            record_message_completed_event=bundle.task.kind == "agent_execution_async",
        )
        self.tool_repository.record_audit_event(
            agent_id=approval.agent_id,
            event_type="approval.denied",
            entity_type="approval",
            entity_id=approval.id,
            payload={"tool_call_id": approval.tool_call_id or ""},
        )

        refreshed_bundle = self.approvals.get_bundle(approval.id)
        assert refreshed_bundle is not None
        assert refreshed_bundle.tool_call is not None

        return ApprovalActionResponse(
            approval=self._serialize_bundle(refreshed_bundle),
            task_run_status=persisted.task_run.status,
            tool_call_status=refreshed_bundle.tool_call.status,
            output_text="Approval denied. Execution ended without running the tool.",
            assistant_message_id=persisted.assistant_message.id
            if persisted.assistant_message is not None
            else None,
        )

    def _require_pending_bundle(self, approval_id: str) -> ApprovalBundle:
        bundle = self.approvals.get_bundle(approval_id)
        if bundle is None:
            msg = "Approval not found."
            raise ValueError(msg)
        if bundle.approval.status != "pending":
            msg = "Approval is not pending."
            raise ValueError(msg)
        return bundle

    def _serialize_bundle(self, bundle: ApprovalBundle) -> ApprovalRead:
        tool_call = bundle.tool_call
        return ApprovalRead(
            id=bundle.approval.id,
            agent_id=bundle.approval.agent_id,
            task_id=bundle.approval.task_id,
            tool_call_id=bundle.approval.tool_call_id,
            kind=bundle.approval.kind,
            requested_action=bundle.approval.requested_action,
            reason=bundle.approval.reason,
            status=bundle.approval.status,
            decided_at=bundle.approval.decided_at,
            expires_at=bundle.approval.expires_at,
            created_at=bundle.approval.created_at,
            updated_at=bundle.approval.updated_at,
            tool_name=tool_call.tool_name if tool_call else None,
            tool_input_json=tool_call.input_json if tool_call else None,
            session_id=bundle.session.id if bundle.session else None,
            session_title=bundle.session.title if bundle.session else None,
            task_run_id=bundle.task_run.id if bundle.task_run else None,
        )

    def _resume_kernel(
        self,
        *,
        request,
        tool_name: str,
        tool_call_id: str,
        tool_arguments: dict[str, object] | None,
        tool_output: str,
    ):
        import asyncio

        return asyncio.run(
            create_agent_kernel(tool_executor=self.tool_service).resume_after_tool(
                request,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                tool_arguments=tool_arguments,
                tool_output=tool_output,
            )
        )
