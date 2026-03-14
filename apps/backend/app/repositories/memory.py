from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlmodel import Session, delete, select

from app.models.entities import (
    AuditEvent,
    MemoryChangeLog,
    MemoryEntry,
    MemoryRecallLog,
    MemoryRelation,
    SessionSummary,
    Setting,
    utc_now,
)


class MemoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_feature_flag(self, key: str, *, default: bool = False) -> bool:
        setting = self.session.exec(
            select(Setting).where(Setting.scope == "features", Setting.key == key)
        ).first()
        if setting is None or setting.value_text is None:
            return default
        return setting.value_text.strip().lower() == "true"

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
        statement = select(MemoryEntry)
        if scope_type is not None:
            statement = statement.where(MemoryEntry.scope_type == scope_type)
        if source_kind is not None:
            statement = statement.where(MemoryEntry.source_kind == source_kind)
        if lifecycle_state is not None:
            statement = statement.where(MemoryEntry.lifecycle_state == lifecycle_state)
        if hidden is not None:
            statement = statement.where(MemoryEntry.hidden_from_recall.is_(hidden))
        if deleted is True:
            statement = statement.where(MemoryEntry.deleted_at.is_not(None))
        elif deleted is False or deleted is None:
            statement = statement.where(MemoryEntry.deleted_at.is_(None))
        if session_id is not None:
            statement = statement.where(MemoryEntry.session_id == session_id)
        if conversation_id is not None:
            statement = statement.where(MemoryEntry.conversation_id == conversation_id)
        if search:
            term = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    MemoryEntry.title.ilike(term),
                    MemoryEntry.body.ilike(term),
                    MemoryEntry.summary.ilike(term),
                )
            )
        statement = statement.order_by(MemoryEntry.created_at.desc()).offset(offset).limit(limit)
        return list(self.session.exec(statement))

    def get_entry(self, memory_id: str) -> MemoryEntry | None:
        return self.session.exec(select(MemoryEntry).where(MemoryEntry.id == memory_id)).first()

    def add_entry(self, entry: MemoryEntry) -> MemoryEntry:
        self.session.add(entry)
        self.session.flush()
        self.session.refresh(entry)
        return entry

    def save_entry(self, entry: MemoryEntry) -> MemoryEntry:
        entry.updated_at = utc_now()
        self.session.add(entry)
        self.session.flush()
        self.session.refresh(entry)
        return entry

    def delete_entry(self, entry: MemoryEntry) -> None:
        self.session.exec(
            delete(MemoryRelation).where(
                or_(
                    MemoryRelation.from_memory_id == entry.id,
                    MemoryRelation.to_memory_id == entry.id,
                )
            )
        )
        self.session.delete(entry)
        self.session.flush()

    def find_active_by_dedupe_hash(
        self,
        dedupe_hash: str,
        *,
        exclude_id: str | None = None,
    ) -> MemoryEntry | None:
        statement = select(MemoryEntry).where(
            MemoryEntry.dedupe_hash == dedupe_hash,
            MemoryEntry.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(MemoryEntry.id != exclude_id)
        return self.session.exec(statement.order_by(MemoryEntry.updated_at.desc())).first()

    def find_user_tombstone_by_dedupe_hash(self, dedupe_hash: str) -> MemoryEntry | None:
        statement = (
            select(MemoryEntry)
            .where(
                MemoryEntry.dedupe_hash == dedupe_hash,
                or_(
                    MemoryEntry.deleted_at.is_not(None),
                    MemoryEntry.hidden_from_recall.is_(True),
                ),
            )
            .order_by(MemoryEntry.updated_at.desc())
        )
        return self.session.exec(statement).first()

    def add_relation(
        self,
        *,
        from_memory_id: str,
        to_memory_id: str,
        relation_kind: str,
        created_by: str,
    ) -> MemoryRelation:
        relation = MemoryRelation(
            from_memory_id=from_memory_id,
            to_memory_id=to_memory_id,
            relation_kind=relation_kind,
            created_by=created_by,
        )
        self.session.add(relation)
        self.session.flush()
        self.session.refresh(relation)
        return relation

    def add_change_log(
        self,
        *,
        memory_id: str,
        action: str,
        actor_type: str,
        actor_id: str | None,
        before_snapshot: dict[str, Any] | None,
        after_snapshot: dict[str, Any] | None,
    ) -> MemoryChangeLog:
        row = MemoryChangeLog(
            memory_id=memory_id,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            before_snapshot=(
                json.dumps(before_snapshot, ensure_ascii=False)
                if before_snapshot is not None
                else None
            ),
            after_snapshot=(
                json.dumps(after_snapshot, ensure_ascii=False)
                if after_snapshot is not None
                else None
            ),
        )
        self.session.add(row)
        self.session.flush()
        self.session.refresh(row)
        return row

    def list_history(self, memory_id: str) -> list[MemoryChangeLog]:
        statement = (
            select(MemoryChangeLog)
            .where(MemoryChangeLog.memory_id == memory_id)
            .order_by(MemoryChangeLog.created_at.asc())
        )
        return list(self.session.exec(statement))

    def add_session_summary(
        self,
        summary: SessionSummary,
    ) -> SessionSummary:
        self.session.add(summary)
        self.session.flush()
        self.session.refresh(summary)
        return summary

    def get_session_summary_by_task_run(self, task_run_id: str | None) -> SessionSummary | None:
        if not task_run_id:
            return None
        statement = select(SessionSummary).where(SessionSummary.task_run_id == task_run_id)
        return self.session.exec(statement).first()

    def list_recent_recall_record_ids(
        self,
        *,
        session_id: str,
        since: datetime,
    ) -> set[str]:
        statement = select(MemoryRecallLog.record_id).where(
            MemoryRecallLog.session_id == session_id,
            MemoryRecallLog.decision == "included",
            MemoryRecallLog.created_at >= since,
            MemoryRecallLog.record_id.is_not(None),
        )
        return {record_id for record_id in self.session.exec(statement) if record_id}

    def record_audit_event(
        self,
        *,
        agent_id: str | None,
        event_type: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, Any],
        summary_text: str,
        level: str = "info",
    ) -> AuditEvent:
        event = AuditEvent(
            agent_id=agent_id,
            actor_type="system",
            level=level,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            summary_text=summary_text,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        self.session.add(event)
        self.session.flush()
        self.session.refresh(event)
        return event

    @staticmethod
    def parse_history_rows(rows: Sequence[MemoryChangeLog]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "id": row.id,
                    "memory_id": row.memory_id,
                    "action": row.action,
                    "actor_type": row.actor_type,
                    "actor_id": row.actor_id,
                    "before_snapshot": json.loads(row.before_snapshot)
                    if row.before_snapshot
                    else None,
                    "after_snapshot": json.loads(row.after_snapshot)
                    if row.after_snapshot
                    else None,
                    "created_at": row.created_at,
                }
            )
        return items
