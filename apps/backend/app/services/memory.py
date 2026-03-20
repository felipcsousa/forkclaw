from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from app.memory.policy import dedupe_hash_for, inspect_manual_text, summarize_text
from app.models.entities import (
    Agent,
    MemoryChangeLog,
    MemoryEntry,
    MemoryRecallLog,
    SessionSummary,
    ensure_utc,
    utc_now,
)
from app.repositories.memory import MemoryRepository
from app.schemas.memory import (
    MemoryEntryCreate,
    MemoryEntryUpdate,
    MemoryHistoryEntryRead,
    MemoryImportance,
    MemoryItemCreate,
    MemoryItemRead,
    MemoryItemUpdate,
    MemoryRecallDetailRead,
    MemoryRecallItemRead,
    MemoryRecallLogEntryRead,
    MemorySearchItemRead,
    SessionRecallSummaryRead,
)
from app.services.memory_admin_service import MemoryAdminService
from app.services.memory_search_service import MemorySearchService

USER_SCOPE_KEY = "local-user"
USER_MANAGED_SOURCE_KINDS = {
    "manual",
    "user_override",
    "promoted_from_session",
    "promoted_from_subagent",
}


@dataclass(frozen=True)
class MemoryRecallCandidate:
    item: MemoryItemRead
    reason: str
    score: float


class MemoryService:
    _BATCH_LOOKUP_CHUNK_SIZE = 200

    def __init__(self, session: Session):
        self.session = session
        self.repository = MemoryRepository(session)
        self.admin = MemoryAdminService(session)
        self.search = MemorySearchService(session)

    def list_items(
        self,
        *,
        kind: str | None = None,
        query: str | None = None,
        scope: str | None = None,
        source_kind: str | None = None,
        state: str | None = None,
        recall_status: str | None = None,
        mode: str = "all",
    ) -> list[MemoryItemRead]:
        items = [
            *[self._read_entry(entry) for entry in self.session.exec(select(MemoryEntry))],
            *[self._read_summary(summary) for summary in self.session.exec(select(SessionSummary))],
        ]
        query_text = (query or "").strip().lower()
        normalized_scope = self._normalize_label(scope)
        filtered: list[MemoryItemRead] = []

        for item in items:
            if kind and item.kind != kind:
                continue
            if normalized_scope and self._normalize_label(item.scope) != normalized_scope:
                continue
            if source_kind and item.source_kind != source_kind:
                continue
            if not self._matches_state_filter(item, state):
                continue
            if recall_status and item.recall_status != recall_status:
                continue
            if mode == "manual" and not item.is_manual:
                continue
            if mode == "automatic" and item.is_manual:
                continue
            if query_text:
                haystack = " ".join(
                    [
                        item.title or "",
                        item.content or "",
                        item.scope or "",
                        item.source_kind or "",
                        item.source_label or "",
                    ]
                ).lower()
                if query_text not in haystack:
                    continue
            filtered.append(item)

        return sorted(filtered, key=lambda item: item.updated_at, reverse=True)

    def get_item(self, memory_id: str) -> MemoryItemRead:
        entry = self.repository.get_entry(memory_id)
        if entry is not None:
            return self._read_entry(entry)

        summary = self.session.get(SessionSummary, memory_id)
        if summary is not None:
            return self._read_summary(summary)

        msg = "Memory item not found."
        raise ValueError(msg)

    def create_item(self, payload: MemoryItemCreate) -> MemoryItemRead:
        if payload.kind == "session_summary":
            return self._create_session_summary_item(payload)

        created = self.admin.create_manual_entry(
            MemoryEntryCreate(
                scope_type="stable" if payload.kind == "stable" else "episodic",
                scope_key=self._scope_key_from_label(payload.scope),
                title=payload.title,
                body=payload.content,
                summary=summarize_text(payload.content),
                importance=self._importance_score(payload.importance),
                confidence=1.0,
            )
        )
        self._enrich_manual_entry(created)
        return self._read_entry(created)

    def update_item(self, memory_id: str, payload: MemoryItemUpdate) -> MemoryItemRead:
        entry = self.repository.get_entry(memory_id)
        if entry is not None:
            if self._is_user_managed(entry.source_kind):
                updated = self.admin.update_entry(
                    memory_id,
                    MemoryEntryUpdate(
                        title=payload.title,
                        body=payload.content,
                        summary=summarize_text(payload.content) if payload.content else None,
                        importance=(
                            self._importance_score(payload.importance)
                            if payload.importance is not None
                            else None
                        ),
                    ),
                )
                return self._read_entry(updated)
            return self._create_entry_override(entry, payload)

        summary = self.session.get(SessionSummary, memory_id)
        if summary is not None:
            if summary.source_kind == "manual":
                return self._update_manual_summary(summary, payload)
            return self._create_summary_override(summary, payload)

        msg = "Memory item not found."
        raise ValueError(msg)

    def hide_item(self, memory_id: str) -> MemoryItemRead:
        entry = self.repository.get_entry(memory_id)
        if entry is not None:
            return self._read_entry(self.admin.hide(memory_id))

        summary = self._require_summary(memory_id)
        summary.hidden_from_recall = True
        return self._save_summary(summary)

    def restore_item(self, memory_id: str) -> MemoryItemRead:
        entry = self.repository.get_entry(memory_id)
        if entry is not None:
            if entry.deleted_at is not None or entry.lifecycle_state == "soft_deleted":
                entry = self.admin.restore(memory_id)
            if entry.hidden_from_recall:
                entry = self.admin.unhide(memory_id)
            return self._read_entry(entry)

        summary = self._require_summary(memory_id)
        summary.hidden_from_recall = False
        summary.deleted_at = None
        return self._save_summary(summary)

    def promote_item(self, memory_id: str) -> MemoryItemRead:
        entry = self.repository.get_entry(memory_id)
        if entry is not None:
            return self._read_entry(self.admin.promote(memory_id))

        summary = self._require_summary(memory_id)
        summary.importance = min(summary.importance + 0.3, 1.0)
        return self._save_summary(summary)

    def demote_item(self, memory_id: str) -> MemoryItemRead:
        entry = self.repository.get_entry(memory_id)
        if entry is not None:
            return self._read_entry(self.admin.demote(memory_id))

        summary = self._require_summary(memory_id)
        summary.importance = max(summary.importance - 0.3, 0.0)
        return self._save_summary(summary)

    def delete_item(self, memory_id: str, *, hard: bool) -> MemoryItemRead | None:
        entry = self.repository.get_entry(memory_id)
        if entry is not None:
            if hard:
                self.admin.hard_delete(memory_id)
                return None
            return self._read_entry(self.admin.soft_delete(memory_id))

        summary = self._require_summary(memory_id)
        if hard:
            self.session.delete(summary)
            self.session.commit()
            return None
        summary.deleted_at = utc_now()
        summary.hidden_from_recall = True
        return self._save_summary(summary)

    def history_for_item(self, memory_id: str) -> list[MemoryHistoryEntryRead]:
        entry = self.repository.get_entry(memory_id)
        if entry is None:
            self._require_summary(memory_id)
            return []

        rows = self.repository.list_history(memory_id)
        return [self._history_item(row) for row in rows]

    def select_for_recall(
        self,
        *,
        input_text: str,
        session_id: str,
        limit: int = 5,
    ) -> list[MemoryRecallCandidate]:
        if not self.repository.get_feature_flag("memory_v1_enabled", default=False):
            return []

        recent_record_ids = self.repository.list_recent_recall_record_ids(
            session_id=session_id,
            since=utc_now() - timedelta(hours=12),
        )
        response = self.search.search(
            q=input_text,
            session_id=session_id,
            scopes=None,
            limit=max(limit * 4, limit),
        )
        return self._filter_and_map_candidates(
            items=response.items,
            recent_record_ids=recent_record_ids,
            limit=limit,
        )

    def _filter_and_map_candidates(
        self,
        items: list[MemorySearchItemRead],
        recent_record_ids: set[str],
        limit: int,
    ) -> list[MemoryRecallCandidate]:
        candidates: list[MemoryRecallCandidate] = []
        current_ids: set[str] = set()
        for item in items:
            score_breakdown = item.score_breakdown or {}
            lexical_score = float(score_breakdown.get("lexical") or 0.0)
            if lexical_score <= 0.0:
                continue
            if item.id in recent_record_ids or item.id in current_ids:
                continue

            candidate = self._map_recall_candidate(item)
            candidates.append(candidate)
            current_ids.add(item.id)
            if len(candidates) >= limit:
                break
        return candidates

    def _map_recall_candidate(self, item: MemorySearchItemRead) -> MemoryRecallCandidate:
        title = item.title or item.summary or item.body or "Memory"
        scope = self._scope_label_from_key(item.origin.scope_key)
        kind = (
            "session_summary"
            if item.record_type == "session_summary"
            else self._kind_from_scope_type(
                item.origin.scope_type,
            )
        )
        source_label = self._source_label(
            item.source_kind,
            is_override=item.override.status == "overrides_automatic",
        )
        importance = self._importance_label(item.importance)
        origin_session_id = item.origin.session_id
        origin_subagent_session_id = (
            item.origin.session_id
            if item.origin.session_id
            and item.origin.root_session_id
            and item.origin.session_id != item.origin.root_session_id
            else None
        )
        reason = self._recall_reason(item)
        return MemoryRecallCandidate(
            item=MemoryItemRead(
                id=item.id,
                kind=kind,
                title=title,
                content=item.body or item.summary or "",
                scope=scope,
                source_kind=item.source_kind,
                source_label=source_label,
                importance=importance,
                state="active",
                recall_status="active",
                is_manual=self._is_user_managed(item.source_kind),
                is_override=item.override.status == "overrides_automatic",
                origin_session_id=origin_session_id,
                origin_subagent_session_id=origin_subagent_session_id,
                original_memory_id=item.override.target_id,
                created_at=utc_now(),
                updated_at=utc_now(),
            ),
            reason=reason,
            score=item.score,
        )

    def inject_recall_context(
        self,
        *,
        input_text: str,
        candidates: list[MemoryRecallCandidate],
    ) -> str:
        if not candidates:
            return input_text

        memory_lines = [
            "Relevant memory for this reply:",
            *[
                (
                    f"- {candidate.item.title} [{candidate.item.kind}/{candidate.item.scope}] "
                    f"{candidate.item.content} ({candidate.reason})"
                )
                for candidate in candidates
            ],
        ]
        return f"{input_text.rstrip()}\n\n" + "\n".join(memory_lines)

    def record_recall_event(
        self,
        *,
        assistant_message_id: str,
        session_id: str,
        task_run_id: str,
        payload: dict[str, object] | None,
    ) -> None:
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items:
            return

        message = self._require_message(assistant_message_id)
        reason_summary = payload.get("reason_summary") if isinstance(payload, dict) else None
        query_text = payload.get("query_text") if isinstance(payload, dict) else None
        normalized_query_text = (
            query_text.strip() if isinstance(query_text, str) and query_text.strip() else None
        )
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "stable")
            record_type = "session_summary" if kind == "session_summary" else "memory_entry"
            memory_id = str(item.get("memory_id") or "")
            if not memory_id:
                continue
            try:
                resolved_item = self.get_item(memory_id)
            except ValueError:
                resolved_item = None
            scope_type = (
                "session_summary"
                if resolved_item is not None and resolved_item.kind == "session_summary"
                else (resolved_item.kind if resolved_item is not None else kind)
            )
            scope_key = (
                resolved_item.scope
                if resolved_item is not None
                else (str(item.get("scope") or "") or message.session_id)
            )
            row = MemoryRecallLog(
                assistant_message_id=assistant_message_id,
                memory_id=memory_id,
                scope_type=scope_type,
                scope_key=scope_key,
                conversation_id=message.conversation_id,
                session_id=session_id,
                run_id=task_run_id,
                query_text=normalized_query_text,
                recall_reason="runtime_context",
                decision="included",
                rank=index,
                record_type=record_type,
                record_id=memory_id,
                reason_json=json.dumps(
                    {
                        "reason": item.get("reason"),
                        "origin_session_id": item.get("origin_session_id"),
                        "origin_subagent_session_id": item.get("origin_subagent_session_id"),
                    },
                    ensure_ascii=False,
                ),
                reason_summary=str(reason_summary) if isinstance(reason_summary, str) else None,
                source_kind=str(item.get("source_kind") or "") or None,
                override_status=(
                    "overrides_automatic" if bool(item.get("original_memory_id")) else "none"
                ),
            )
            self.session.add(row)
        self.session.commit()

    def recall_for_message(self, assistant_message_id: str) -> MemoryRecallDetailRead:
        message = self._require_message(assistant_message_id)
        rows = self._recall_rows_for_message(assistant_message_id)
        if not rows:
            return MemoryRecallDetailRead(
                assistant_message_id=assistant_message_id,
                session_id=message.session_id,
                created_at=message.created_at,
                reason_summary=None,
                items=[],
            )
        first = rows[0]

        record_ids = [row.record_id or row.memory_id or "" for row in rows]
        items_map = self._batch_get_items([rid for rid in record_ids if rid])

        return MemoryRecallDetailRead(
            assistant_message_id=assistant_message_id,
            session_id=first.session_id or message.session_id,
            created_at=first.created_at,
            reason_summary=first.reason_summary,
            items=[
                self._recall_item_read(row, items_map.get(row.record_id or row.memory_id or ""))
                for row in rows
            ],
        )

    def recall_for_session(self, session_id: str) -> list[SessionRecallSummaryRead]:
        statement = (
            select(MemoryRecallLog)
            .where(MemoryRecallLog.session_id == session_id)
            .order_by(MemoryRecallLog.created_at.desc(), MemoryRecallLog.rank.asc())
        )
        grouped = self._group_recall_rows(list(self.session.exec(statement)))

        all_record_ids = []
        for _, rows in grouped:
            all_record_ids.extend([row.record_id or row.memory_id or "" for row in rows])
        items_map = self._batch_get_items([rid for rid in all_record_ids if rid])

        return [
            SessionRecallSummaryRead(
                assistant_message_id=assistant_message_id,
                created_at=rows[0].created_at,
                recalled_count=len(rows),
                reason_summary=rows[0].reason_summary,
                items=[
                    self._recall_item_read(row, items_map.get(row.record_id or row.memory_id or ""))
                    for row in rows
                ],
            )
            for assistant_message_id, rows in grouped
        ]

    def recall_log(self) -> list[MemoryRecallLogEntryRead]:
        statement = (
            select(MemoryRecallLog)
            .where(MemoryRecallLog.assistant_message_id.is_not(None))
            .order_by(MemoryRecallLog.created_at.desc(), MemoryRecallLog.rank.asc())
        )
        grouped = self._group_recall_rows(list(self.session.exec(statement)))

        all_record_ids = []
        for _, rows in grouped:
            all_record_ids.extend([row.record_id or row.memory_id or "" for row in rows])
        items_map = self._batch_get_items([rid for rid in all_record_ids if rid])

        return [
            MemoryRecallLogEntryRead(
                id=rows[0].id,
                assistant_message_id=assistant_message_id,
                session_id=rows[0].session_id or "",
                task_run_id=rows[0].run_id,
                created_at=rows[0].created_at,
                reason_summary=rows[0].reason_summary,
                items=[
                    self._recall_item_read(row, items_map.get(row.record_id or row.memory_id or ""))
                    for row in rows
                ],
            )
            for assistant_message_id, rows in grouped
        ]

    def _batch_get_items(self, memory_ids: list[str]) -> dict[str, MemoryItemRead]:
        if not memory_ids:
            return {}
        unique_ids = list(dict.fromkeys(memory_ids))
        items_map: dict[str, MemoryItemRead] = {}
        for chunk in self._iter_lookup_chunks(unique_ids):
            entries = self.session.exec(select(MemoryEntry).where(MemoryEntry.id.in_(chunk)))
            for entry in entries:
                items_map[entry.id] = self._read_entry(entry)

        missing_ids = [m_id for m_id in unique_ids if m_id not in items_map]
        for chunk in self._iter_lookup_chunks(missing_ids):
            summaries = self.session.exec(
                select(SessionSummary).where(SessionSummary.id.in_(chunk))
            )
            for summary in summaries:
                items_map[summary.id] = self._read_summary(summary)

        return items_map

    def _iter_lookup_chunks(self, memory_ids: list[str]):
        for index in range(0, len(memory_ids), self._BATCH_LOOKUP_CHUNK_SIZE):
            yield memory_ids[index : index + self._BATCH_LOOKUP_CHUNK_SIZE]

    def _create_session_summary_item(self, payload: MemoryItemCreate) -> MemoryItemRead:
        default_agent = self._require_default_agent()
        summary = SessionSummary(
            agent_id=default_agent.id,
            scope_key=self._scope_key_from_label(payload.scope),
            session_id=None,
            root_session_id=None,
            conversation_id=None,
            parent_session_id=None,
            task_run_id=None,
            source_kind="manual",
            summary_text=payload.content.strip(),
            importance=self._importance_score(payload.importance),
            created_by="user",
            workspace_path=None,
            user_scope_key=USER_SCOPE_KEY,
            hidden_from_recall=False,
            deleted_at=None,
            origin_message_id=None,
            origin_task_run_id=None,
            override_target_summary_id=None,
        )
        return self._save_summary(summary, title_override=payload.title, update_timestamp=False)

    def _save_summary(
        self,
        summary: SessionSummary,
        *,
        title_override: str | None = None,
        update_timestamp: bool = True,
    ) -> MemoryItemRead:
        if update_timestamp:
            summary.updated_at = utc_now()
        self.session.add(summary)
        self.session.commit()
        self.session.refresh(summary)
        return self._read_summary(summary, title_override=title_override)

    def _update_manual_summary(
        self,
        summary: SessionSummary,
        payload: MemoryItemUpdate,
    ) -> MemoryItemRead:
        content = (payload.content or summary.summary_text).strip()
        summary.summary_text = content
        if payload.importance is not None:
            summary.importance = self._importance_score(payload.importance)
        if payload.scope is not None:
            summary.scope_key = self._scope_key_from_label(payload.scope)
        return self._save_summary(summary, title_override=payload.title)

    def _create_entry_override(
        self,
        entry: MemoryEntry,
        payload: MemoryItemUpdate,
    ) -> MemoryItemRead:
        override = self._build_override_entry(entry, payload)

        entry.hidden_from_recall = True
        entry.updated_by = "user"
        entry.updated_at = utc_now()

        self.session.add(entry)
        created = self.repository.add_entry(override)

        self._record_override_change_logs(entry.id, created.id)

        self.session.commit()
        self.session.refresh(created)
        self.session.refresh(entry)

        return self._read_entry(created)

    def _build_override_entry(
        self,
        entry: MemoryEntry,
        payload: MemoryItemUpdate,
    ) -> MemoryEntry:
        title = (payload.title or entry.title).strip()
        content = (payload.content or entry.body).strip()
        inspected = inspect_manual_text(
            title=title,
            body=content,
            summary=summarize_text(content),
        )
        return MemoryEntry(
            agent_id=entry.agent_id,
            scope_type=entry.scope_type,
            scope_key=entry.scope_key,
            conversation_id=entry.conversation_id,
            session_id=entry.session_id,
            root_session_id=entry.root_session_id,
            parent_session_id=entry.parent_session_id,
            source_kind="manual",
            lifecycle_state="active",
            title=inspected.title,
            body=inspected.body,
            summary=inspected.summary,
            importance=(
                self._importance_score(payload.importance)
                if payload.importance is not None
                else entry.importance
            ),
            confidence=1.0,
            dedupe_hash=dedupe_hash_for(inspected.title, inspected.body, inspected.summary),
            created_by="user",
            updated_by="user",
            workspace_path=entry.workspace_path,
            user_scope_key=entry.user_scope_key,
            expires_at=None,
            redaction_state=inspected.redaction_state,
            security_state=inspected.security_state,
            hidden_from_recall=False,
            deleted_at=None,
            origin_message_id=entry.origin_message_id,
            origin_task_run_id=entry.origin_task_run_id,
            override_target_entry_id=entry.id,
        )

    def _record_override_change_logs(
        self,
        original_entry_id: str,
        override_entry_id: str,
    ) -> None:
        self.repository.add_change_log(
            memory_id=original_entry_id,
            action="override_created",
            actor_type="user",
            actor_id="memory-studio",
            before_snapshot={"id": original_entry_id},
            after_snapshot={"override_id": override_entry_id},
        )
        self.repository.add_change_log(
            memory_id=override_entry_id,
            action="create",
            actor_type="user",
            actor_id="memory-studio",
            before_snapshot=None,
            after_snapshot={"override_target_entry_id": original_entry_id},
        )

    def _create_summary_override(
        self,
        summary: SessionSummary,
        payload: MemoryItemUpdate,
    ) -> MemoryItemRead:
        override = SessionSummary(
            agent_id=summary.agent_id,
            scope_key=payload.scope
            and self._scope_key_from_label(payload.scope)
            or summary.scope_key,
            session_id=summary.session_id,
            root_session_id=summary.root_session_id,
            conversation_id=summary.conversation_id,
            parent_session_id=summary.parent_session_id,
            task_run_id=summary.task_run_id,
            source_kind="manual",
            summary_text=(payload.content or summary.summary_text).strip(),
            importance=(
                self._importance_score(payload.importance)
                if payload.importance is not None
                else summary.importance
            ),
            created_by="user",
            workspace_path=summary.workspace_path,
            user_scope_key=summary.user_scope_key,
            hidden_from_recall=False,
            deleted_at=None,
            origin_message_id=summary.origin_message_id,
            origin_task_run_id=summary.origin_task_run_id,
            override_target_summary_id=summary.id,
        )
        summary.hidden_from_recall = True
        summary.updated_at = utc_now()
        self.session.add(summary)
        self.session.add(override)
        self.session.commit()
        self.session.refresh(override)
        return self._read_summary(override, title_override=payload.title)

    def _enrich_manual_entry(self, entry: MemoryEntry) -> None:
        default_agent = self._require_default_agent()
        entry.agent_id = default_agent.id
        entry.user_scope_key = USER_SCOPE_KEY
        entry.updated_at = utc_now()
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)

    def _read_entry(self, entry: MemoryEntry) -> MemoryItemRead:
        return MemoryItemRead(
            id=entry.id,
            kind=self._kind_from_scope_type(entry.scope_type),
            title=entry.title,
            content=entry.body,
            scope=self._scope_label_from_key(entry.scope_key),
            source_kind=entry.source_kind,
            source_label=self._source_label(
                entry.source_kind,
                is_override=bool(entry.override_target_entry_id),
            ),
            importance=self._importance_label(entry.importance),
            state="deleted" if entry.deleted_at is not None else "active",
            recall_status="hidden" if entry.hidden_from_recall else "active",
            is_manual=self._is_user_managed(entry.source_kind),
            is_override=bool(entry.override_target_entry_id),
            origin_session_id=entry.session_id,
            origin_subagent_session_id=entry.session_id if entry.parent_session_id else None,
            original_memory_id=entry.override_target_entry_id,
            created_at=ensure_utc(entry.created_at),
            updated_at=ensure_utc(entry.updated_at),
        )

    def _read_summary(
        self,
        summary: SessionSummary,
        *,
        title_override: str | None = None,
    ) -> MemoryItemRead:
        title = (title_override or summarize_text(summary.summary_text, limit=80)).strip()
        return MemoryItemRead(
            id=summary.id,
            kind="session_summary",
            title=title,
            content=summary.summary_text,
            scope=self._scope_label_from_key(summary.scope_key),
            source_kind=summary.source_kind,
            source_label=self._source_label(
                summary.source_kind,
                is_override=bool(summary.override_target_summary_id),
            ),
            importance=self._importance_label(summary.importance),
            state="deleted" if summary.deleted_at is not None else "active",
            recall_status="hidden" if summary.hidden_from_recall else "active",
            is_manual=summary.source_kind == "manual",
            is_override=bool(summary.override_target_summary_id),
            origin_session_id=summary.session_id,
            origin_subagent_session_id=summary.session_id if summary.parent_session_id else None,
            original_memory_id=summary.override_target_summary_id,
            created_at=ensure_utc(summary.created_at),
            updated_at=ensure_utc(summary.updated_at),
        )

    def _history_item(self, row: MemoryChangeLog) -> MemoryHistoryEntryRead:
        snapshot = self._parse_json(row.after_snapshot) or self._parse_json(row.before_snapshot)
        return MemoryHistoryEntryRead(
            id=row.id,
            memory_id=row.memory_id,
            action=self._history_action_label(row.action),
            summary=self._history_summary(row.action),
            snapshot=snapshot,
            created_at=ensure_utc(row.created_at),
        )

    def _recall_rows_for_message(self, assistant_message_id: str) -> list[MemoryRecallLog]:
        statement = (
            select(MemoryRecallLog)
            .where(MemoryRecallLog.assistant_message_id == assistant_message_id)
            .order_by(MemoryRecallLog.rank.asc(), MemoryRecallLog.created_at.asc())
        )
        return list(self.session.exec(statement))

    def _group_recall_rows(
        self,
        rows: list[MemoryRecallLog],
    ) -> list[tuple[str, list[MemoryRecallLog]]]:
        grouped: dict[str, list[MemoryRecallLog]] = {}
        order: list[str] = []
        for row in rows:
            if not row.assistant_message_id:
                continue
            if row.assistant_message_id not in grouped:
                grouped[row.assistant_message_id] = []
                order.append(row.assistant_message_id)
            grouped[row.assistant_message_id].append(row)
        return [
            (assistant_message_id, grouped[assistant_message_id]) for assistant_message_id in order
        ]

    def _recall_item_read(
        self,
        row: MemoryRecallLog,
        preloaded_item: MemoryItemRead | None = None,
    ) -> MemoryRecallItemRead:
        if preloaded_item is not None:
            item = preloaded_item
        else:
            try:
                item = self.get_item(row.record_id or row.memory_id or "")
            except ValueError:
                item = self._deleted_recall_item(row)
        reason_payload = self._parse_json(row.reason_json)
        return MemoryRecallItemRead(
            memory_id=item.id,
            title=item.title,
            kind=item.kind,
            scope=item.scope,
            source_kind=item.source_kind,
            source_label=item.source_label,
            importance=item.importance,
            reason=str(
                reason_payload.get("reason") or row.recall_reason or "Matched runtime context."
            ),
            origin_session_id=(
                reason_payload.get("origin_session_id")
                if isinstance(reason_payload.get("origin_session_id"), str)
                else item.origin_session_id
            ),
            origin_subagent_session_id=(
                reason_payload.get("origin_subagent_session_id")
                if isinstance(reason_payload.get("origin_subagent_session_id"), str)
                else item.origin_subagent_session_id
            ),
        )

    def _deleted_recall_item(self, row: MemoryRecallLog) -> MemoryItemRead:
        kind = self._deleted_item_kind(row)
        source_kind = row.source_kind or ("summary" if kind == "session_summary" else "manual")
        return MemoryItemRead(
            id=row.record_id or row.memory_id or "",
            kind=kind,
            title="Deleted session summary" if kind == "session_summary" else "Deleted memory",
            content="",
            scope=self._scope_label_from_key(row.scope_key),
            source_kind=source_kind,
            source_label=self._source_label(
                source_kind,
                is_override=row.override_status == "overrides_automatic",
            ),
            importance="medium",
            state="deleted",
            recall_status="hidden",
            is_manual=self._is_user_managed(source_kind),
            is_override=row.override_status == "overrides_automatic",
            origin_session_id=None,
            origin_subagent_session_id=None,
            original_memory_id=None,
            created_at=ensure_utc(row.created_at),
            updated_at=ensure_utc(row.updated_at),
        )

    @staticmethod
    def _deleted_item_kind(row: MemoryRecallLog) -> str:
        if row.record_type == "session_summary" or row.scope_type == "session_summary":
            return "session_summary"
        if row.scope_type == "episodic":
            return "episodic"
        return "stable"

    def _recall_reason(self, item) -> str:  # noqa: ANN001
        matched_scopes = ", ".join(item.origin.matched_scopes) or "default scopes"
        lexical = item.score_breakdown.get("lexical")
        preview_source = item.body or item.summary or item.title or "memory context"
        preview = " ".join(str(preview_source).split())[:72]
        if isinstance(lexical, (int, float)):
            return f"Matched {matched_scopes}; lexical score {lexical:.2f}; context: {preview}"
        return f"Matched {matched_scopes}; context: {preview}"

    def _require_default_agent(self) -> Agent:
        statement = select(Agent).where(Agent.is_default.is_(True)).order_by(Agent.created_at.asc())
        agent = self.session.exec(statement).first()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)
        return agent

    def _require_summary(self, memory_id: str) -> SessionSummary:
        summary = self.session.get(SessionSummary, memory_id)
        if summary is None:
            msg = "Memory item not found."
            raise ValueError(msg)
        return summary

    def _require_message(self, message_id: str):
        from app.models.entities import Message

        message = self.session.get(Message, message_id)
        if message is None:
            msg = "Message not found."
            raise ValueError(msg)
        return message

    @staticmethod
    def _importance_score(importance: MemoryImportance) -> float:
        return {
            "low": 0.2,
            "medium": 0.5,
            "high": 0.9,
        }[importance]

    @staticmethod
    def _importance_label(value: float | None) -> MemoryImportance:
        if value is None:
            return "medium"
        if value >= 0.8:
            return "high"
        if value >= 0.45:
            return "medium"
        return "low"

    @staticmethod
    def _kind_from_scope_type(scope_type: str | None) -> str:
        if scope_type == "episodic":
            return "episodic"
        return "stable"

    @staticmethod
    def _source_label(source_kind: str, *, is_override: bool) -> str:
        if is_override and source_kind == "manual":
            return "Manual override"
        return {
            "manual": "Manual",
            "automatic": "Session capture",
            "autosaved": "Session capture",
            "summary": "Conversation summary",
            "promoted_from_session": "Promoted",
            "promoted_from_subagent": "Promoted",
            "user_override": "Manual override",
        }.get(source_kind, source_kind.replace("_", " ").title())

    @staticmethod
    def _scope_key_from_label(scope: str) -> str:
        normalized = MemoryService._normalize_label(scope) or "global"
        return f"user/{normalized}"

    @staticmethod
    def _scope_label_from_key(scope_key: str | None) -> str:
        if not scope_key:
            return "global"
        if scope_key.startswith("user/"):
            return scope_key.split("/", 1)[1]
        if ":" in scope_key:
            return scope_key.split(":", 1)[1]
        return scope_key

    @staticmethod
    def _normalize_label(value: str | None) -> str:
        return " ".join((value or "").split()).strip().lower()

    @staticmethod
    def _is_user_managed(source_kind: str) -> bool:
        return source_kind in USER_MANAGED_SOURCE_KINDS

    @staticmethod
    def _matches_state_filter(item: MemoryItemRead, state: str | None) -> bool:
        if state == "hidden":
            return item.state != "deleted" and item.recall_status == "hidden"
        if state == "deleted":
            return item.state == "deleted"
        if state == "active" or state is None:
            return item.state == "active"
        return True

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
    def _history_action_label(action: str) -> str:
        return {
            "create": "created",
            "edit": "updated",
            "hide_from_recall": "hidden",
            "unhide_from_recall": "restored",
            "restore": "restored",
            "soft_delete": "soft_deleted",
            "hard_delete": "hard_deleted",
        }.get(action, action)

    @staticmethod
    def _history_summary(action: str) -> str:
        return {
            "create": "Memory created.",
            "edit": "Memory updated.",
            "hide_from_recall": "Memory hidden from recall.",
            "unhide_from_recall": "Memory restored.",
            "restore": "Memory restored.",
            "soft_delete": "Memory moved to deleted state.",
            "hard_delete": "Memory permanently deleted.",
            "override_created": "Manual override created.",
        }.get(action, "Memory updated.")
