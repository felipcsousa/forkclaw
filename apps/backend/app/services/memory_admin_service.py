from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from app.memory.policy import (
    dedupe_hash_for,
    inspect_manual_text,
    validate_scope_key,
    validate_scope_type,
)
from app.models.entities import MemoryEntry
from app.repositories.memory import MemoryRepository
from app.schemas.memory import MemoryEntryCreate, MemoryEntryUpdate


class MemoryFeatureDisabledError(RuntimeError):
    pass


class MemoryManualCrudDisabledError(RuntimeError):
    pass


class MemoryHardDeleteDisabledError(RuntimeError):
    pass


@dataclass(frozen=True)
class MemoryConflictError(RuntimeError):
    existing_memory_id: str
    reason: str


class MemoryAdminService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = MemoryRepository(session)

    def ensure_memory_v1_enabled(self) -> None:
        if not self.repository.get_feature_flag("memory_v1_enabled", default=False):
            raise MemoryFeatureDisabledError("Memory V1 is disabled.")

    def ensure_manual_crud_enabled(self) -> None:
        self.ensure_memory_v1_enabled()
        if not self.repository.get_feature_flag("memory_manual_crud_enabled", default=False):
            raise MemoryManualCrudDisabledError("Memory manual CRUD is disabled.")

    def list_entries(
        self,
        *,
        limit: int,
        offset: int,
        scope_type: str | None,
        source_kind: str | None,
        lifecycle_state: str | None,
        hidden: bool | None,
        deleted: bool | None,
        session_id: str | None,
        conversation_id: str | None,
        search: str | None,
    ) -> list[MemoryEntry]:
        self.ensure_memory_v1_enabled()
        return self.repository.list_entries(
            limit=limit,
            offset=offset,
            scope_type=scope_type,
            source_kind=source_kind,
            lifecycle_state=lifecycle_state,
            hidden=hidden,
            deleted=deleted,
            session_id=session_id,
            conversation_id=conversation_id,
            search=search,
        )

    def get_entry(self, memory_id: str) -> MemoryEntry:
        self.ensure_memory_v1_enabled()
        entry = self.repository.get_entry(memory_id)
        if entry is None:
            msg = "Memory entry not found."
            raise ValueError(msg)
        return entry

    def create_manual_entry(self, payload: MemoryEntryCreate) -> MemoryEntry:
        self.ensure_manual_crud_enabled()
        return self._commit_action(lambda: self._create_manual_entry(payload))

    def update_entry(self, memory_id: str, payload: MemoryEntryUpdate) -> MemoryEntry:
        self.ensure_manual_crud_enabled()
        return self._commit_action(lambda: self._update_entry(memory_id, payload))

    def hide(self, memory_id: str) -> MemoryEntry:
        self.ensure_manual_crud_enabled()
        return self._commit_action(lambda: self._toggle_hidden(memory_id, hidden=True))

    def unhide(self, memory_id: str) -> MemoryEntry:
        self.ensure_manual_crud_enabled()
        return self._commit_action(lambda: self._toggle_hidden(memory_id, hidden=False))

    def promote(self, memory_id: str) -> MemoryEntry:
        self.ensure_manual_crud_enabled()
        return self._commit_action(lambda: self._promote(memory_id))

    def demote(self, memory_id: str) -> MemoryEntry:
        self.ensure_manual_crud_enabled()
        return self._commit_action(lambda: self._demote(memory_id))

    def soft_delete(self, memory_id: str) -> MemoryEntry:
        self.ensure_manual_crud_enabled()
        return self._commit_action(lambda: self._soft_delete(memory_id))

    def restore(self, memory_id: str) -> MemoryEntry:
        self.ensure_manual_crud_enabled()
        return self._commit_action(lambda: self._restore(memory_id))

    def hard_delete(self, memory_id: str) -> dict[str, bool]:
        self.ensure_manual_crud_enabled()
        if not self.repository.get_feature_flag("memory_hard_delete_enabled", default=False):
            raise MemoryHardDeleteDisabledError("Hard delete is disabled.")
        return self._commit_action(lambda: self._hard_delete(memory_id))

    def list_history(self, memory_id: str) -> list[dict[str, Any]]:
        self.ensure_memory_v1_enabled()
        self.get_entry(memory_id)
        return self.repository.parse_history_rows(self.repository.list_history(memory_id))

    def _create_manual_entry(self, payload: MemoryEntryCreate) -> MemoryEntry:
        scope_type = validate_scope_type(payload.scope_type)
        scope_key = validate_scope_key(payload.scope_key)
        inspected = inspect_manual_text(
            title=payload.title,
            body=payload.body,
            summary=payload.summary,
        )
        dedupe_hash = dedupe_hash_for(inspected.title, inspected.body, inspected.summary)
        self._raise_if_conflict(dedupe_hash)
        entry = MemoryEntry(
            scope_type=scope_type,
            scope_key=scope_key,
            conversation_id=payload.conversation_id,
            session_id=payload.session_id,
            parent_session_id=payload.parent_session_id,
            source_kind="manual",
            lifecycle_state="active",
            title=inspected.title,
            body=inspected.body,
            summary=inspected.summary,
            importance=payload.importance,
            confidence=payload.confidence,
            dedupe_hash=dedupe_hash,
            created_by="user",
            updated_by="user",
            expires_at=payload.expires_at,
            redaction_state=inspected.redaction_state,
            security_state=inspected.security_state,
            hidden_from_recall=False,
            deleted_at=None,
        )
        created = self.repository.add_entry(entry)
        self.repository.add_change_log(
            memory_id=created.id,
            action="create",
            actor_type="user",
            actor_id="api",
            before_snapshot=None,
            after_snapshot=self._snapshot(created),
        )
        return created

    def _update_entry(self, memory_id: str, payload: MemoryEntryUpdate) -> MemoryEntry:
        entry = self._require_entry(memory_id)
        before = self._snapshot(entry)
        title = payload.title if payload.title is not None else entry.title
        body = payload.body if payload.body is not None else entry.body
        summary = payload.summary if payload.summary is not None else entry.summary
        inspected = inspect_manual_text(title=title, body=body, summary=summary)
        dedupe_hash = dedupe_hash_for(inspected.title, inspected.body, inspected.summary)
        self._raise_if_conflict(dedupe_hash, exclude_id=entry.id)

        content_changed = (
            inspected.title != entry.title
            or inspected.body != entry.body
            or inspected.summary != entry.summary
        )
        entry.title = inspected.title
        entry.body = inspected.body
        entry.summary = inspected.summary
        entry.dedupe_hash = dedupe_hash
        entry.redaction_state = inspected.redaction_state
        entry.security_state = inspected.security_state
        if payload.importance is not None:
            entry.importance = payload.importance
        if payload.confidence is not None:
            entry.confidence = payload.confidence
        entry.expires_at = payload.expires_at
        if content_changed and entry.source_kind in {"autosaved", "summary"}:
            entry.source_kind = "user_override"
        entry.updated_by = "user"
        saved = self.repository.save_entry(entry)
        self.repository.add_change_log(
            memory_id=saved.id,
            action="edit",
            actor_type="user",
            actor_id="api",
            before_snapshot=before,
            after_snapshot=self._snapshot(saved),
        )
        return saved

    def _toggle_hidden(self, memory_id: str, *, hidden: bool) -> MemoryEntry:
        entry = self._require_entry(memory_id)
        before = self._snapshot(entry)
        entry.hidden_from_recall = hidden
        entry.updated_by = "user"
        saved = self.repository.save_entry(entry)
        self.repository.add_change_log(
            memory_id=saved.id,
            action="hide_from_recall" if hidden else "unhide_from_recall",
            actor_type="user",
            actor_id="api",
            before_snapshot=before,
            after_snapshot=self._snapshot(saved),
        )
        return saved

    def _promote(self, memory_id: str) -> MemoryEntry:
        entry = self._require_entry(memory_id)
        before = self._snapshot(entry)
        entry.scope_type = "stable"
        entry.source_kind = (
            "promoted_from_subagent"
            if entry.parent_session_id is not None
            else "promoted_from_session"
        )
        entry.updated_by = "user"
        saved = self.repository.save_entry(entry)
        self.repository.add_relation(
            from_memory_id=saved.id,
            to_memory_id=saved.id,
            relation_kind=saved.source_kind,
            created_by="user",
        )
        self.repository.add_change_log(
            memory_id=saved.id,
            action="promote",
            actor_type="user",
            actor_id="api",
            before_snapshot=before,
            after_snapshot=self._snapshot(saved),
        )
        return saved

    def _demote(self, memory_id: str) -> MemoryEntry:
        entry = self._require_entry(memory_id)
        before = self._snapshot(entry)
        entry.scope_type = "episodic"
        entry.updated_by = "user"
        saved = self.repository.save_entry(entry)
        self.repository.add_change_log(
            memory_id=saved.id,
            action="demote",
            actor_type="user",
            actor_id="api",
            before_snapshot=before,
            after_snapshot=self._snapshot(saved),
        )
        return saved

    def _soft_delete(self, memory_id: str) -> MemoryEntry:
        entry = self._require_entry(memory_id)
        before = self._snapshot(entry)
        entry.lifecycle_state = "soft_deleted"
        entry.deleted_at = datetime.now(UTC)
        entry.updated_by = "user"
        saved = self.repository.save_entry(entry)
        self.repository.add_change_log(
            memory_id=saved.id,
            action="soft_delete",
            actor_type="user",
            actor_id="api",
            before_snapshot=before,
            after_snapshot=self._snapshot(saved),
        )
        return saved

    def _restore(self, memory_id: str) -> MemoryEntry:
        entry = self._require_entry(memory_id)
        before = self._snapshot(entry)
        entry.lifecycle_state = "active"
        entry.deleted_at = None
        entry.updated_by = "user"
        saved = self.repository.save_entry(entry)
        self.repository.add_change_log(
            memory_id=saved.id,
            action="restore",
            actor_type="user",
            actor_id="api",
            before_snapshot=before,
            after_snapshot=self._snapshot(saved),
        )
        return saved

    def _hard_delete(self, memory_id: str) -> dict[str, bool]:
        entry = self._require_entry(memory_id)
        before = self._snapshot(entry)
        self.repository.add_change_log(
            memory_id=entry.id,
            action="hard_delete",
            actor_type="user",
            actor_id="api",
            before_snapshot=before,
            after_snapshot=None,
        )
        self.repository.delete_entry(entry)
        return {"deleted": True}

    def _require_entry(self, memory_id: str) -> MemoryEntry:
        entry = self.repository.get_entry(memory_id)
        if entry is None:
            msg = "Memory entry not found."
            raise ValueError(msg)
        return entry

    def _raise_if_conflict(self, dedupe_hash: str, *, exclude_id: str | None = None) -> None:
        conflict = self.repository.find_active_by_dedupe_hash(dedupe_hash, exclude_id=exclude_id)
        if conflict is None:
            return
        raise MemoryConflictError(
            existing_memory_id=conflict.id,
            reason="dedupe_hash_match",
        )

    def _snapshot(self, entry: MemoryEntry) -> dict[str, Any]:
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
            "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
            "redaction_state": entry.redaction_state,
            "security_state": entry.security_state,
            "hidden_from_recall": entry.hidden_from_recall,
            "deleted_at": entry.deleted_at.isoformat() if entry.deleted_at else None,
        }

    def _commit_action(self, action):
        try:
            result = action()
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise
