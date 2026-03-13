from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.memory.policy import (
    build_conversation_identity,
    dedupe_hash_for,
    inspect_automatic_text,
    summarize_text,
)
from app.models.entities import MemoryEntry, SessionRecord, SessionSummary, TaskRun
from app.repositories.memory import MemoryRepository


class MemoryCaptureService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = MemoryRepository(session)

    def capture_execution_result(
        self,
        *,
        session_record: SessionRecord,
        task_run: TaskRun | None,
        output_text: str,
    ) -> MemoryEntry | None:
        if not self.repository.get_feature_flag("memory_v1_enabled", default=False):
            return None
        if not output_text.strip():
            return None
        if (
            task_run is not None
            and self.repository.get_session_summary_by_task_run(task_run.id) is not None
        ):
            return None

        identity = build_conversation_identity(
            session_id=session_record.id,
            conversation_id=session_record.conversation_id,
            run_id=task_run.id if task_run is not None else None,
            parent_session_id=session_record.parent_session_id,
        )
        title = summarize_text(output_text, limit=200)
        summary_text = summarize_text(output_text)
        inspected = inspect_automatic_text(title=title, body=output_text, summary=summary_text)
        dedupe_hash = dedupe_hash_for(inspected.title, inspected.body, inspected.summary)

        suppressed = self.repository.find_user_tombstone_by_dedupe_hash(dedupe_hash)
        if suppressed is not None:
            self.repository.record_audit_event(
                agent_id=session_record.agent_id,
                event_type="memory.capture.suppressed",
                entity_type="memory_entry",
                entity_id=suppressed.id,
                payload={
                    "session_id": session_record.id,
                    "task_run_id": task_run.id if task_run is not None else None,
                    "dedupe_hash": dedupe_hash,
                },
                summary_text="Automatic memory capture suppressed by a user tombstone.",
                level="warning",
            )
            summary = SessionSummary(
                agent_id=session_record.agent_id,
                scope_key=identity.session_key,
                session_id=session_record.id,
                root_session_id=session_record.root_session_id or session_record.id,
                conversation_id=identity.conversation_id,
                parent_session_id=session_record.parent_session_id,
                task_run_id=task_run.id if task_run is not None else None,
                source_kind="summary",
                summary_text=summary_text,
                importance=0.0,
                created_by="system",
                workspace_path=None,
                user_scope_key="local-user",
                hidden_from_recall=False,
                deleted_at=None,
                origin_message_id=None,
                origin_task_run_id=task_run.id if task_run is not None else None,
                override_target_summary_id=None,
            )
            self.repository.add_session_summary(summary)
            return None

        existing = self.repository.find_active_by_dedupe_hash(dedupe_hash)
        if existing is not None:
            return existing

        summary = SessionSummary(
            agent_id=session_record.agent_id,
            scope_key=identity.session_key,
            session_id=session_record.id,
            root_session_id=session_record.root_session_id or session_record.id,
            conversation_id=identity.conversation_id,
            parent_session_id=session_record.parent_session_id,
            task_run_id=task_run.id if task_run is not None else None,
            source_kind="summary",
            summary_text=summary_text,
            importance=0.0,
            created_by="system",
            workspace_path=None,
            user_scope_key="local-user",
            hidden_from_recall=False,
            deleted_at=None,
            origin_message_id=None,
            origin_task_run_id=task_run.id if task_run is not None else None,
            override_target_summary_id=None,
        )
        self.repository.add_session_summary(summary)

        entry = MemoryEntry(
            agent_id=session_record.agent_id,
            scope_type="episodic",
            scope_key=identity.session_key,
            conversation_id=identity.conversation_id,
            session_id=session_record.id,
            root_session_id=session_record.root_session_id or session_record.id,
            parent_session_id=session_record.parent_session_id,
            source_kind="autosaved",
            lifecycle_state="active",
            title=inspected.title,
            body=inspected.body,
            summary=inspected.summary,
            importance=0.4,
            confidence=0.5,
            dedupe_hash=dedupe_hash,
            created_by="system",
            updated_by="system",
            workspace_path=None,
            user_scope_key="local-user",
            expires_at=None,
            redaction_state=inspected.redaction_state,
            security_state=inspected.security_state,
            hidden_from_recall=False,
            deleted_at=None,
            origin_message_id=None,
            origin_task_run_id=task_run.id if task_run is not None else None,
            override_target_entry_id=None,
        )
        created = self.repository.add_entry(entry)
        self.repository.add_change_log(
            memory_id=created.id,
            action="create",
            actor_type="system",
            actor_id="capture",
            before_snapshot=None,
            after_snapshot=self._snapshot(created, identity.to_dict()),
        )
        return created

    def _snapshot(
        self,
        entry: MemoryEntry,
        conversation_identity: dict[str, str | None],
    ) -> dict[str, Any]:
        return {
            "id": entry.id,
            "scope_type": entry.scope_type,
            "scope_key": entry.scope_key,
            "conversation_id": entry.conversation_id,
            "session_id": entry.session_id,
            "parent_session_id": entry.parent_session_id,
            "source_kind": entry.source_kind,
            "lifecycle_state": entry.lifecycle_state,
            "title": entry.title,
            "body": entry.body,
            "summary": entry.summary,
            "importance": entry.importance,
            "confidence": entry.confidence,
            "dedupe_hash": entry.dedupe_hash,
            "created_by": entry.created_by,
            "updated_by": entry.updated_by,
            "conversation_identity": conversation_identity,
        }
