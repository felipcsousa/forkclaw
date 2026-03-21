from __future__ import annotations

from uuid import uuid4

from sqlmodel import Session

from app.repositories.acp import AcpRepository
from app.schemas.acp import (
    AcpCancelResponse,
    AcpLoadSessionResponse,
    AcpNewSessionResponse,
    AcpPromptResponse,
    AcpSessionRead,
    AcpTranscriptMessageRead,
)
from app.services.agent_execution import AgentExecutionService
from app.services.agent_os import AgentOSService


class AcpService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = AcpRepository(session)
        self.execution = AgentExecutionService(session)
        self.agent_os = AgentOSService(session)

    def is_enabled(self) -> bool:
        setting = self.repository.get_setting("features", "acp_bridge_enabled")
        if setting is None:
            return False
        value = (setting.value_text or "").strip().lower()
        return value in {"1", "true", "yes", "on", "enabled"}

    def set_enabled(self, enabled: bool) -> bool:
        self.repository.upsert_setting(
            scope="features",
            key="acp_bridge_enabled",
            value_type="boolean",
            value_text="true" if enabled else "false",
        )
        self.session.commit()
        return enabled

    def list_sessions(self) -> list[AcpSessionRead]:
        return [AcpSessionRead.model_validate(item) for item in self.repository.list_mappings()]

    def create_session(
        self,
        *,
        label: str,
        runtime: str = "acp",
        parent_session_id: str | None = None,
        backend_session_id: str | None = None,
        child_session_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AcpNewSessionResponse:
        self._ensure_enabled()
        if backend_session_id is None and child_session_id is None:
            session_record = self.agent_os.create_session(title=label)
            backend_session_id = session_record.id
        session_key = f"acp_{uuid4().hex}"
        mapping = self.repository.create_session_mapping(
            session_key=session_key,
            label=label.strip() or "ACP Session",
            runtime=runtime.strip() or "acp",
            status="active",
            parent_session_id=parent_session_id,
            backend_session_id=backend_session_id,
            child_session_id=child_session_id,
            metadata=metadata,
        )
        self.session.commit()
        return AcpNewSessionResponse(
            session_key=session_key,
            mapping=AcpSessionRead.model_validate(mapping),
        )

    def prompt(self, *, session_key: str, text: str) -> AcpPromptResponse:
        self._ensure_enabled()
        mapping = self.repository.get_mapping_by_key(session_key)
        if mapping is None:
            msg = "ACP session not found."
            raise ValueError(msg)
        if mapping.status != "active":
            msg = f"ACP session is not active (status={mapping.status})."
            raise ValueError(msg)
        target_session_id = mapping.child_session_id or mapping.backend_session_id
        if not target_session_id:
            msg = "ACP session has no target backend session."
            raise ValueError(msg)

        response = self.execution.execute_simple(
            session_id=target_session_id,
            title=None,
            message=text,
        )
        self.repository.touch_prompt(mapping)
        self.session.commit()
        return AcpPromptResponse(
            session_key=session_key,
            output_text=response.output_text,
            session_id=target_session_id,
            task_run_id=response.task_run_id,
            assistant_message_id=response.assistant_message_id,
        )

    def cancel(self, *, session_key: str) -> AcpCancelResponse:
        self._ensure_enabled()
        mapping = self.repository.get_mapping_by_key(session_key)
        if mapping is None:
            msg = "ACP session not found."
            raise ValueError(msg)
        mapping.status = "cancelled"
        self.repository.save_mapping(mapping)
        self.session.commit()
        return AcpCancelResponse(session_key=session_key, status=mapping.status)

    def load_session(self, *, session_key: str, limit: int) -> AcpLoadSessionResponse:
        self._ensure_enabled()
        mapping = self.repository.get_mapping_by_key(session_key)
        if mapping is None:
            msg = "ACP session not found."
            raise ValueError(msg)
        target_session_id = mapping.child_session_id or mapping.backend_session_id
        if not target_session_id:
            msg = "ACP session has no target backend session."
            raise ValueError(msg)
        messages = self.repository.list_messages_for_session(target_session_id, limit=limit)
        return AcpLoadSessionResponse(
            session_key=session_key,
            session_id=target_session_id,
            messages=[
                AcpTranscriptMessageRead(
                    id=item.id,
                    role=item.role,
                    sequence_number=item.sequence_number,
                    content_text=item.content_text,
                    created_at=item.created_at,
                )
                for item in messages
            ],
        )

    def _ensure_enabled(self) -> None:
        if self.is_enabled():
            return
        msg = "ACP bridge is disabled. Enable it before creating or using ACP sessions."
        raise ValueError(msg)
