from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from typing import Any

from sqlmodel import Session

from app.models.entities import MemoryEntry, SessionSummary, ensure_utc
from app.repositories.memory_search import (
    MemoryCandidate,
    MemorySearchRepository,
    ResolvedMemoryContext,
)
from app.schemas.memory import (
    MemoryItemRead,
    MemoryOriginRead,
    MemoryOverrideRead,
    MemoryRecallPreviewResponse,
    MemoryScopeContextRead,
    MemoryScopeName,
    MemoryScopesResponse,
    MemoryScopeSupportRead,
    MemorySearchResponse,
)


class MemorySearchService:
    USER_SCOPE_KEY = "local-user"
    SUPPORTED_SCOPES: tuple[MemoryScopeName, ...] = (
        "current_conversation",
        "current_session_tree",
        "agent",
        "user",
        "workspace",
    )

    def __init__(
        self,
        session: Session,
        *,
        repository: MemorySearchRepository | None = None,
    ):
        self.session = session
        self.repository = repository or MemorySearchRepository(session)

    def search(
        self,
        *,
        q: str,
        session_id: str | None,
        scopes: list[MemoryScopeName] | None,
        limit: int,
    ) -> MemorySearchResponse:
        query_text, normalized_query, fts_query = self._normalize_query(q)
        context = self._resolve_context(session_id)
        applied_scopes = self._resolve_scopes(scopes, context)
        items = self._collect_items(
            fts_query=fts_query,
            context=context,
            applied_scopes=applied_scopes,
            limit=limit,
            substitute_overrides=False,
        )
        return MemorySearchResponse(
            query=query_text,
            normalized_query=normalized_query,
            applied_scopes=applied_scopes,
            context=self._context_read(context),
            items=items,
        )

    def recall_preview(
        self,
        *,
        q: str,
        session_id: str | None,
        scopes: list[MemoryScopeName] | None,
        limit: int,
        run_id: str | None,
    ) -> MemoryRecallPreviewResponse:
        query_text, normalized_query, fts_query = self._normalize_query(q)
        context = self._resolve_context(session_id)
        applied_scopes = self._resolve_scopes(scopes, context)
        items = self._collect_items(
            fts_query=fts_query,
            context=context,
            applied_scopes=applied_scopes,
            limit=limit,
            substitute_overrides=True,
        )
        self.repository.create_recall_logs(
            [
                {
                    "query_text": normalized_query,
                    "run_id": run_id,
                    "record_type": item.record_type,
                    "record_id": item.id,
                    "score": item.score,
                    "reason": {
                        "matched_scopes": item.origin.matched_scopes,
                        "score_breakdown": item.score_breakdown,
                        "selected_via_substitution": item.override.selected_via_substitution,
                        "substituted_for_id": item.override.target_id
                        if item.override.selected_via_substitution
                        else None,
                        "effective_id": item.override.effective_id,
                    },
                    "source_kind": item.source_kind,
                    "override_status": item.override.status,
                }
                for item in items
            ]
        )
        return MemoryRecallPreviewResponse(
            query=query_text,
            normalized_query=normalized_query,
            applied_scopes=applied_scopes,
            context=self._context_read(context),
            items=items,
            run_id=run_id,
        )

    def list_scopes(self, *, session_id: str | None) -> MemoryScopesResponse:
        context = self._resolve_context(session_id)
        default_scopes = self._default_scopes(context)
        return MemoryScopesResponse(
            context=self._context_read(context),
            default_scopes=default_scopes,
            supported_scopes=[
                MemoryScopeSupportRead(
                    name=scope,
                    available=self._scope_available(scope, context),
                )
                for scope in self.SUPPORTED_SCOPES
            ],
        )

    def _collect_items(
        self,
        *,
        fts_query: str,
        context: ResolvedMemoryContext,
        applied_scopes: list[MemoryScopeName],
        limit: int,
        substitute_overrides: bool,
    ) -> list[MemoryItemRead]:
        candidate_limit = max(limit * 5, 25)
        candidates = self.repository.search_memory_entries(
            fts_query=fts_query,
            selected_scopes=list(applied_scopes),
            context=context,
            limit=candidate_limit,
        ) + self.repository.search_session_summaries(
            fts_query=fts_query,
            selected_scopes=list(applied_scopes),
            context=context,
            limit=candidate_limit,
        )

        memory_overrides = self.repository.list_memory_entry_overrides(
            [
                item.id
                for item in candidates
                if item.record_type == "memory_entry" and item.source_kind == "automatic"
            ]
        )
        session_summary_overrides = self.repository.list_session_summary_overrides(
            [
                item.id
                for item in candidates
                if item.record_type == "session_summary" and item.source_kind == "automatic"
            ]
        )

        working_items = self._prepare_working_items(
            candidates=candidates,
            applied_scopes=applied_scopes,
            context=context,
            memory_overrides=memory_overrides,
            session_summary_overrides=session_summary_overrides,
            substitute_overrides=substitute_overrides,
        )
        ranked = self._rank_working_items(working_items)
        return [self._build_item_read(item) for item in ranked[:limit]]

    def _prepare_working_items(
        self,
        *,
        candidates: list[MemoryCandidate],
        applied_scopes: list[MemoryScopeName],
        context: ResolvedMemoryContext,
        memory_overrides: dict[str, MemoryEntry],
        session_summary_overrides: dict[str, SessionSummary],
        substitute_overrides: bool,
    ) -> list[dict[str, Any]]:
        prepared: dict[tuple[str, str], dict[str, Any]] = {}
        for candidate in candidates:
            matched_scopes = self._matched_scopes(candidate, applied_scopes, context)
            if not matched_scopes:
                continue

            override_row = None
            if candidate.record_type == "memory_entry" and candidate.source_kind == "automatic":
                override_row = memory_overrides.get(candidate.id)
            elif (
                candidate.record_type == "session_summary"
                and candidate.source_kind == "automatic"
            ):
                override_row = session_summary_overrides.get(candidate.id)

            effective_candidate = candidate
            override_status = "none"
            target_id = None
            selected_via_substitution = False
            if candidate.override_target_id:
                override_status = "overrides_automatic"
                target_id = candidate.override_target_id
            elif override_row is not None:
                override_status = "overridden_by_manual"
                target_id = override_row.id
                if substitute_overrides:
                    if override_row.hidden_from_recall:
                        continue
                    effective_candidate = self._candidate_from_override_row(
                        candidate=candidate,
                        override_row=override_row,
                        record_type=candidate.record_type,
                    )
                    override_status = "overrides_automatic"
                    target_id = candidate.id
                    selected_via_substitution = True

            dedupe_key = (effective_candidate.record_type, effective_candidate.id)
            existing = prepared.get(dedupe_key)
            payload = {
                "candidate": effective_candidate,
                "matched_scopes": matched_scopes,
                "override_status": override_status,
                "target_id": target_id,
                "selected_via_substitution": selected_via_substitution,
                "lexical_source_id": candidate.id,
                "substituted_for_id": candidate.id if selected_via_substitution else None,
            }
            if existing is None:
                prepared[dedupe_key] = payload
                continue
            existing["matched_scopes"] = sorted(
                set(existing["matched_scopes"]) | set(matched_scopes),
            )
            existing["selected_via_substitution"] = (
                existing["selected_via_substitution"] or selected_via_substitution
            )
            if payload["candidate"].lexical_score > existing["candidate"].lexical_score:
                existing["candidate"] = payload["candidate"]
                existing["lexical_source_id"] = payload["lexical_source_id"]
            if payload["override_status"] == "overrides_automatic":
                existing["override_status"] = payload["override_status"]
                existing["target_id"] = payload["target_id"]
            existing["substituted_for_id"] = existing["substituted_for_id"] or payload[
                "substituted_for_id"
            ]
        return list(prepared.values())

    def _rank_working_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for item in items:
            candidate = item["candidate"]
            recency_boost = self._recency_boost(candidate)
            manual_boost = 0.75 if candidate.source_kind == "manual" else 0.0
            importance_boost = candidate.importance
            pre_duplicate = (
                candidate.lexical_score + recency_boost + importance_boost + manual_boost
            )
            item["score"] = pre_duplicate
            item["score_breakdown"] = {
                "lexical": round(candidate.lexical_score, 6),
                "recency": recency_boost,
                "importance": round(importance_boost, 6),
                "manual": manual_boost,
                "duplicate_penalty": 0.0,
                "pre_duplicate_total": round(pre_duplicate, 6),
                "final": round(pre_duplicate, 6),
            }

        ordered = sorted(
            items,
            key=lambda item: (
                -item["score"],
                -item["candidate"].updated_at.timestamp(),
                item["candidate"].id,
            ),
        )
        seen_hashes: dict[str, int] = {}
        for item in ordered:
            content_hash = self._content_hash(item["candidate"])
            duplicates_before = seen_hashes.get(content_hash, 0)
            duplicate_penalty = -0.2 * duplicates_before
            item["score"] = round(item["score"] + duplicate_penalty, 6)
            item["score_breakdown"]["duplicate_penalty"] = round(duplicate_penalty, 6)
            item["score_breakdown"]["final"] = item["score"]
            seen_hashes[content_hash] = duplicates_before + 1
        return ordered

    def _build_item_read(self, item: dict[str, Any]) -> MemoryItemRead:
        candidate = item["candidate"]
        return MemoryItemRead(
            record_type=candidate.record_type,
            id=candidate.id,
            summary=candidate.summary,
            body=candidate.body,
            source_kind=candidate.source_kind,
            importance=candidate.importance,
            score=item["score"],
            score_breakdown=item["score_breakdown"],
            origin=MemoryOriginRead(
                table=candidate.table_name,
                agent_id=candidate.agent_id,
                session_id=candidate.session_id,
                root_session_id=candidate.root_session_id,
                origin_message_id=candidate.origin_message_id,
                origin_task_run_id=candidate.origin_task_run_id,
                workspace_path=candidate.workspace_path,
                matched_scopes=item["matched_scopes"],
            ),
            override=MemoryOverrideRead(
                status=item["override_status"],
                target_id=item["target_id"],
                effective_id=candidate.id,
                selected_via_substitution=item["selected_via_substitution"],
            ),
        )

    def _resolve_context(self, session_id: str | None) -> ResolvedMemoryContext:
        session_record = None
        if session_id is not None:
            session_record = self.repository.get_session(session_id)
            if session_record is None:
                msg = "Session not found."
                raise ValueError(msg)
        default_agent = self.repository.get_default_agent()
        return ResolvedMemoryContext(
            agent_id=(
                session_record.agent_id
                if session_record is not None
                else (default_agent.id if default_agent is not None else None)
            ),
            session_id=session_record.id if session_record is not None else None,
            root_session_id=(
                (session_record.root_session_id or session_record.id)
                if session_record is not None
                else None
            ),
            workspace_path=self.repository.get_workspace_root(),
            user_scope_key=self.USER_SCOPE_KEY,
        )

    def _resolve_scopes(
        self,
        scopes: list[MemoryScopeName] | None,
        context: ResolvedMemoryContext,
    ) -> list[MemoryScopeName]:
        resolved = list(dict.fromkeys(scopes or self._default_scopes(context)))
        needs_session = {
            "current_conversation",
            "current_session_tree",
        } & set(resolved)
        if needs_session and context.session_id is None:
            msg = "session_id is required for current conversation or session tree scopes."
            raise ValueError(msg)
        return resolved

    def _default_scopes(self, context: ResolvedMemoryContext) -> list[MemoryScopeName]:
        if context.session_id is not None:
            return list(self.SUPPORTED_SCOPES)
        return ["agent", "user", "workspace"]

    def _matched_scopes(
        self,
        candidate: MemoryCandidate,
        applied_scopes: list[MemoryScopeName],
        context: ResolvedMemoryContext,
    ) -> list[MemoryScopeName]:
        matched: list[MemoryScopeName] = []
        if (
            "current_conversation" in applied_scopes
            and context.session_id is not None
            and candidate.session_id == context.session_id
        ):
            matched.append("current_conversation")
        if (
            "current_session_tree" in applied_scopes
            and context.root_session_id is not None
            and candidate.root_session_id == context.root_session_id
        ):
            matched.append("current_session_tree")
        if (
            "agent" in applied_scopes
            and context.agent_id is not None
            and candidate.agent_id == context.agent_id
        ):
            matched.append("agent")
        if (
            "user" in applied_scopes
            and context.user_scope_key is not None
            and candidate.user_scope_key == context.user_scope_key
        ):
            matched.append("user")
        if (
            "workspace" in applied_scopes
            and context.workspace_path is not None
            and candidate.workspace_path == context.workspace_path
        ):
            matched.append("workspace")
        return matched

    def _scope_available(
        self,
        scope: MemoryScopeName,
        context: ResolvedMemoryContext,
    ) -> bool:
        if scope == "current_conversation":
            return context.session_id is not None
        if scope == "current_session_tree":
            return context.root_session_id is not None
        if scope == "agent":
            return context.agent_id is not None
        if scope == "user":
            return context.user_scope_key is not None
        return context.workspace_path is not None

    @staticmethod
    def _context_read(context: ResolvedMemoryContext) -> MemoryScopeContextRead:
        return MemoryScopeContextRead(
            agent_id=context.agent_id,
            session_id=context.session_id,
            root_session_id=context.root_session_id,
            workspace_path=context.workspace_path,
            user_scope_key=context.user_scope_key,
        )

    @staticmethod
    def _normalize_query(q: str) -> tuple[str, str, str]:
        query_text = (q or "").strip()
        if not query_text:
            msg = "Query cannot be blank."
            raise ValueError(msg)
        tokens = re.findall(r"\w+", query_text.lower(), flags=re.UNICODE)
        if not tokens:
            msg = "Query must contain searchable text."
            raise ValueError(msg)
        normalized_query = " ".join(tokens)
        fts_query = " OR ".join(f'"{token}"' for token in tokens)
        return query_text, normalized_query, fts_query

    @staticmethod
    def _recency_boost(candidate: MemoryCandidate) -> float:
        age = max(candidate.updated_at, candidate.created_at)
        elapsed = MemorySearchService._now() - age
        if elapsed <= timedelta(days=1):
            return 0.6
        if elapsed <= timedelta(days=7):
            return 0.3
        if elapsed <= timedelta(days=30):
            return 0.1
        return 0.0

    @staticmethod
    def _candidate_from_override_row(
        *,
        candidate: MemoryCandidate,
        override_row: MemoryEntry | SessionSummary,
        record_type: str,
    ) -> MemoryCandidate:
        table_name = "memory_entries" if record_type == "memory_entry" else "session_summaries"
        body = override_row.body if isinstance(override_row, MemoryEntry) else None
        override_target_id = (
            override_row.override_target_entry_id
            if isinstance(override_row, MemoryEntry)
            else override_row.override_target_summary_id
        )
        return MemoryCandidate(
            record_type=record_type,
            table_name=table_name,
            id=override_row.id,
            body=body,
            summary=override_row.summary,
            source_kind=override_row.source_kind,
            importance=override_row.importance,
            agent_id=override_row.agent_id,
            session_id=override_row.session_id,
            root_session_id=override_row.root_session_id,
            workspace_path=override_row.workspace_path,
            user_scope_key=override_row.user_scope_key,
            origin_message_id=override_row.origin_message_id,
            origin_task_run_id=override_row.origin_task_run_id,
            override_target_id=override_target_id,
            created_at=ensure_utc(override_row.created_at),
            updated_at=ensure_utc(override_row.updated_at),
            lexical_score=candidate.lexical_score,
        )

    @staticmethod
    def _content_hash(candidate: MemoryCandidate) -> str:
        normalized = " ".join(
            part.strip().lower()
            for part in [candidate.summary or "", candidate.body or ""]
            if part and part.strip()
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _now():
        from app.models.entities import utc_now

        return utc_now()
