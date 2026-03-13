from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.entities import (
    Agent,
    MemoryEntry,
    MemoryRecallLog,
    SessionRecord,
    SessionSummary,
    Setting,
    ensure_utc,
    utc_now,
)


@dataclass(frozen=True)
class ResolvedMemoryContext:
    agent_id: str | None
    session_id: str | None
    root_session_id: str | None
    workspace_path: str | None
    user_scope_key: str | None


@dataclass(frozen=True)
class MemoryCandidate:
    record_type: str
    table_name: str
    id: str
    title: str | None
    body: str | None
    summary: str | None
    source_kind: str
    importance: float
    agent_id: str | None
    scope_type: str | None
    scope_key: str | None
    session_id: str | None
    root_session_id: str | None
    workspace_path: str | None
    user_scope_key: str | None
    origin_message_id: str | None
    origin_task_run_id: str | None
    override_target_id: str | None
    created_at: datetime
    updated_at: datetime
    lexical_score: float


class MemorySearchRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_default_agent(self) -> Agent | None:
        statement = select(Agent).where(Agent.is_default.is_(True)).order_by(Agent.created_at.asc())
        return self.session.exec(statement).first()

    def get_session(self, session_id: str) -> SessionRecord | None:
        statement = select(SessionRecord).where(SessionRecord.id == session_id)
        return self.session.exec(statement).first()

    def get_workspace_root(self) -> str:
        statement = select(Setting).where(
            Setting.scope == "security",
            Setting.key == "workspace_root",
        )
        setting = self.session.exec(statement).first()
        if setting is not None and setting.value_text:
            return setting.value_text
        return str(get_settings().default_workspace_root)

    def search_memory_entries(
        self,
        *,
        fts_query: str,
        selected_scopes: list[str],
        context: ResolvedMemoryContext,
        limit: int,
    ) -> list[MemoryCandidate]:
        return self._run_search(
            fts_table="memory_entries_fts",
            base_table="memory_entries",
            table_name="memory_entries",
            select_columns="""
                me.id AS id,
                me.title AS title,
                me.body AS body,
                me.summary AS summary,
                me.source_kind AS source_kind,
                me.importance AS importance,
                me.agent_id AS agent_id,
                me.scope_type AS scope_type,
                me.scope_key AS scope_key,
                me.session_id AS session_id,
                me.root_session_id AS root_session_id,
                me.workspace_path AS workspace_path,
                me.user_scope_key AS user_scope_key,
                me.origin_message_id AS origin_message_id,
                me.origin_task_run_id AS origin_task_run_id,
                me.override_target_entry_id AS override_target_id,
                me.created_at AS created_at,
                me.updated_at AS updated_at,
                CAST(-bm25(memory_entries_fts, 1.0, 0.7) AS FLOAT) AS lexical_score
            """,
            where_prefix="""
                me.hidden_from_recall = 0
                AND me.deleted_at IS NULL
            """,
            fts_query=fts_query,
            selected_scopes=selected_scopes,
            context=context,
            limit=limit,
            record_type="memory_entry",
            order_by="lexical_score DESC, me.updated_at DESC, me.id ASC",
            join_alias="me",
        )

    def search_session_summaries(
        self,
        *,
        fts_query: str,
        selected_scopes: list[str],
        context: ResolvedMemoryContext,
        limit: int,
    ) -> list[MemoryCandidate]:
        return self._run_search(
            fts_table="session_summaries_fts",
            base_table="session_summaries",
            table_name="session_summaries",
            select_columns="""
                ss.id AS id,
                NULL AS title,
                NULL AS body,
                ss.summary_text AS summary,
                ss.source_kind AS source_kind,
                ss.importance AS importance,
                ss.agent_id AS agent_id,
                NULL AS scope_type,
                ss.scope_key AS scope_key,
                ss.session_id AS session_id,
                ss.root_session_id AS root_session_id,
                ss.workspace_path AS workspace_path,
                ss.user_scope_key AS user_scope_key,
                ss.origin_message_id AS origin_message_id,
                ss.origin_task_run_id AS origin_task_run_id,
                ss.override_target_summary_id AS override_target_id,
                ss.created_at AS created_at,
                ss.updated_at AS updated_at,
                CAST(-bm25(session_summaries_fts) AS FLOAT) AS lexical_score
            """,
            where_prefix="""
                ss.hidden_from_recall = 0
                AND ss.deleted_at IS NULL
            """,
            fts_query=fts_query,
            selected_scopes=selected_scopes,
            context=context,
            limit=limit,
            record_type="session_summary",
            order_by="lexical_score DESC, ss.updated_at DESC, ss.id ASC",
            join_alias="ss",
        )

    def list_memory_entry_overrides(self, target_ids: list[str]) -> dict[str, MemoryEntry]:
        if not target_ids:
            return {}
        statement = select(MemoryEntry).where(
            MemoryEntry.override_target_entry_id.in_(target_ids),
            MemoryEntry.source_kind == "manual",
            MemoryEntry.deleted_at.is_(None),
        )
        return {
            item.override_target_entry_id: item
            for item in self.session.exec(statement)
            if item.override_target_entry_id is not None
        }

    def list_session_summary_overrides(self, target_ids: list[str]) -> dict[str, SessionSummary]:
        if not target_ids:
            return {}
        statement = select(SessionSummary).where(
            SessionSummary.override_target_summary_id.in_(target_ids),
            SessionSummary.source_kind == "manual",
            SessionSummary.deleted_at.is_(None),
        )
        return {
            item.override_target_summary_id: item
            for item in self.session.exec(statement)
            if item.override_target_summary_id is not None
        }

    def create_recall_logs(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        now = utc_now()
        for item in items:
            row = MemoryRecallLog(
                query_text=item["query_text"],
                run_id=item.get("run_id"),
                record_type=item["record_type"],
                record_id=item["record_id"],
                score=item["score"],
                reason_json=json.dumps(item["reason"], ensure_ascii=False, sort_keys=True),
                source_kind=item["source_kind"],
                override_status=item["override_status"],
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
        self.session.commit()

    def _run_search(
        self,
        *,
        fts_table: str,
        base_table: str,
        table_name: str,
        select_columns: str,
        where_prefix: str,
        fts_query: str,
        selected_scopes: list[str],
        context: ResolvedMemoryContext,
        limit: int,
        record_type: str,
        order_by: str,
        join_alias: str,
    ) -> list[MemoryCandidate]:
        scope_clause, params = self._scope_clause(
            selected_scopes=selected_scopes,
            context=context,
            alias=join_alias,
        )
        if scope_clause is None:
            return []
        query = sa.text(
            f"""
            SELECT
                {select_columns}
            FROM {fts_table}
            JOIN {base_table} AS {join_alias}
                ON {join_alias}.rowid = {fts_table}.rowid
            WHERE {fts_table} MATCH :fts_query
              AND {where_prefix}
              AND ({scope_clause})
            ORDER BY {order_by}
            LIMIT :limit
            """
        )
        result = self.session.connection().execute(
            query,
            {
                **params,
                "fts_query": fts_query,
                "limit": limit,
            },
        )
        rows = result.mappings().fetchall()
        return [self._candidate_from_row(record_type, table_name, row) for row in rows]

    def _scope_clause(
        self,
        *,
        selected_scopes: list[str],
        context: ResolvedMemoryContext,
        alias: str,
    ) -> tuple[str | None, dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if "current_conversation" in selected_scopes and context.session_id is not None:
            clauses.append(f"{alias}.session_id = :session_id")
            params["session_id"] = context.session_id
        if "current_session_tree" in selected_scopes and context.root_session_id is not None:
            clauses.append(f"{alias}.root_session_id = :root_session_id")
            params["root_session_id"] = context.root_session_id
        if "agent" in selected_scopes and context.agent_id is not None:
            clauses.append(f"{alias}.agent_id = :agent_id")
            params["agent_id"] = context.agent_id
        if "user" in selected_scopes and context.user_scope_key is not None:
            clauses.append(f"{alias}.user_scope_key = :user_scope_key")
            params["user_scope_key"] = context.user_scope_key
        if "workspace" in selected_scopes and context.workspace_path is not None:
            clauses.append(f"{alias}.workspace_path = :workspace_path")
            params["workspace_path"] = context.workspace_path
        if not clauses:
            return None, params
        return " OR ".join(clauses), params

    @staticmethod
    def _candidate_from_row(
        record_type: str,
        table_name: str,
        row: sa.RowMapping,
    ) -> MemoryCandidate:
        return MemoryCandidate(
            record_type=record_type,
            table_name=table_name,
            id=row["id"],
            title=row["title"],
            body=row["body"],
            summary=row["summary"],
            source_kind=row["source_kind"],
            importance=float(row["importance"] or 0.0),
            agent_id=row["agent_id"],
            scope_type=row["scope_type"],
            scope_key=row["scope_key"],
            session_id=row["session_id"],
            root_session_id=row["root_session_id"],
            workspace_path=row["workspace_path"],
            user_scope_key=row["user_scope_key"],
            origin_message_id=row["origin_message_id"],
            origin_task_run_id=row["origin_task_run_id"],
            override_target_id=row["override_target_id"],
            created_at=MemorySearchRepository._parse_datetime(row["created_at"]),
            updated_at=MemorySearchRepository._parse_datetime(row["updated_at"]),
            lexical_score=float(row["lexical_score"] or 0.0),
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return ensure_utc(value)
        if isinstance(value, str):
            return ensure_utc(datetime.fromisoformat(value))
        msg = f"Unsupported datetime value: {value!r}"
        raise TypeError(msg)
