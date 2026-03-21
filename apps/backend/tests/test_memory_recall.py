from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_db_session
from app.models.entities import (
    Agent,
    MemoryEntry,
    MemoryRecallLog,
    SessionRecord,
    SessionSummary,
    Setting,
    utc_now,
)
from app.repositories.agent_execution import AgentExecutionRepository
from app.services.memory import MemoryService


def _default_agent_id() -> str:
    with get_db_session() as session:
        agent = session.exec(select(Agent).where(Agent.is_default.is_(True))).one()
    return agent.id


def _workspace_root(test_client: TestClient) -> str:
    response = test_client.get("/settings/operational")
    assert response.status_code == 200
    return response.json()["workspace_root"]


def _set_feature_flag(key: str, enabled: bool) -> None:
    with get_db_session() as session:
        setting = session.exec(
            select(Setting).where(Setting.scope == "features", Setting.key == key)
        ).one()
        setting.value_text = "true" if enabled else "false"
        session.add(setting)
        session.commit()


def _create_session(test_client: TestClient, title: str) -> dict:
    response = test_client.post("/sessions", json={"title": title})
    assert response.status_code == 201
    return response.json()


def _resolve_conversation_id(
    session: Session,
    conversation_id: str | None,
    session_id: str | None,
) -> str | None:
    if conversation_id is not None:
        return conversation_id
    if session_id is not None:
        session_record = session.get(SessionRecord, session_id)
        return session_record.conversation_id if session_record is not None else None
    return None


def _resolve_scope_key(
    session_id: str | None,
    agent_id: str | None,
    user_scope_key: str | None,
    workspace_path: str | None,
) -> str:
    if session_id is not None:
        return f"session:{session_id}"
    if agent_id is not None:
        return f"agent:{agent_id}"
    if user_scope_key is not None:
        return f"user/{user_scope_key}"
    if workspace_path is not None:
        return f"workspace:{workspace_path}"
    return "agent:default"


def _build_memory_entry(
    session: Session,
    *,
    body: str,
    title: str | None = None,
    summary: str | None = None,
    source_kind: str = "autosaved",
    importance: float = 0.0,
    agent_id: str | None = None,
    session_id: str | None = None,
    root_session_id: str | None = None,
    workspace_path: str | None = None,
    user_scope_key: str | None = None,
    hidden_from_recall: bool = False,
    deleted_at=None,
    override_target_entry_id: str | None = None,
    conversation_id: str | None = None,
) -> MemoryEntry:
    resolved_conversation_id = _resolve_conversation_id(session, conversation_id, session_id)
    normalized_source = "autosaved" if source_kind == "automatic" else source_kind
    resolved_scope_type = "episodic" if session_id is not None else "stable"
    resolved_scope_key = _resolve_scope_key(
        session_id, agent_id, user_scope_key, workspace_path
    )
    return MemoryEntry(
        scope_type=resolved_scope_type,
        scope_key=resolved_scope_key,
        lifecycle_state="active",
        title=title or f"memory-{uuid4().hex[:8]}",
        body=body,
        summary=summary,
        source_kind=normalized_source,
        importance=importance,
        confidence=0.5,
        dedupe_hash=f"dedupe-{uuid4().hex}",
        created_by="user" if normalized_source == "manual" else "system",
        updated_by="user" if normalized_source == "manual" else "system",
        agent_id=agent_id,
        conversation_id=resolved_conversation_id,
        session_id=session_id,
        root_session_id=root_session_id,
        workspace_path=workspace_path,
        user_scope_key=user_scope_key,
        hidden_from_recall=hidden_from_recall,
        deleted_at=deleted_at,
        redaction_state="clean",
        security_state="safe",
        override_target_entry_id=override_target_entry_id,
    )


def _insert_memory_entry(
    *,
    body: str,
    title: str | None = None,
    summary: str | None = None,
    source_kind: str = "autosaved",
    importance: float = 0.0,
    agent_id: str | None = None,
    session_id: str | None = None,
    root_session_id: str | None = None,
    workspace_path: str | None = None,
    user_scope_key: str | None = None,
    hidden_from_recall: bool = False,
    deleted_at=None,
    override_target_entry_id: str | None = None,
    conversation_id: str | None = None,
) -> MemoryEntry:
    with get_db_session() as session:
        entry = _build_memory_entry(
            session,
            body=body,
            title=title,
            summary=summary,
            source_kind=source_kind,
            importance=importance,
            agent_id=agent_id,
            session_id=session_id,
            root_session_id=root_session_id,
            workspace_path=workspace_path,
            user_scope_key=user_scope_key,
            hidden_from_recall=hidden_from_recall,
            deleted_at=deleted_at,
            override_target_entry_id=override_target_entry_id,
            conversation_id=conversation_id,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


def _build_session_summary(
    session: Session,
    *,
    summary: str,
    source_kind: str = "summary",
    importance: float = 0.0,
    agent_id: str | None = None,
    session_id: str | None = None,
    root_session_id: str | None = None,
    workspace_path: str | None = None,
    user_scope_key: str | None = None,
    hidden_from_recall: bool = False,
    deleted_at=None,
    override_target_summary_id: str | None = None,
    conversation_id: str | None = None,
) -> SessionSummary:
    resolved_conversation_id = _resolve_conversation_id(session, conversation_id, session_id)
    normalized_source = "summary" if source_kind == "automatic" else source_kind
    return SessionSummary(
        scope_key=f"session:{session_id or uuid4().hex}",
        summary_text=summary,
        source_kind=normalized_source,
        importance=importance,
        agent_id=agent_id,
        conversation_id=resolved_conversation_id,
        session_id=session_id,
        root_session_id=root_session_id,
        created_by="user" if normalized_source == "manual" else "system",
        workspace_path=workspace_path,
        user_scope_key=user_scope_key,
        hidden_from_recall=hidden_from_recall,
        deleted_at=deleted_at,
        override_target_summary_id=override_target_summary_id,
    )


def _insert_session_summary(
    *,
    summary: str,
    source_kind: str = "summary",
    importance: float = 0.0,
    agent_id: str | None = None,
    session_id: str | None = None,
    root_session_id: str | None = None,
    workspace_path: str | None = None,
    user_scope_key: str | None = None,
    hidden_from_recall: bool = False,
    deleted_at=None,
    override_target_summary_id: str | None = None,
    conversation_id: str | None = None,
) -> SessionSummary:
    with get_db_session() as session:
        item = _build_session_summary(
            session,
            summary=summary,
            source_kind=source_kind,
            importance=importance,
            agent_id=agent_id,
            session_id=session_id,
            root_session_id=root_session_id,
            workspace_path=workspace_path,
            user_scope_key=user_scope_key,
            hidden_from_recall=hidden_from_recall,
            deleted_at=deleted_at,
            override_target_summary_id=override_target_summary_id,
            conversation_id=conversation_id,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


def _make_search_item(
    *,
    item_id: str,
    lexical: float,
    recency: float,
    score: float = 1.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id,
        title=f"title-{item_id}",
        summary=f"summary-{item_id}",
        body=f"body-{item_id}",
        record_type="session_summary",
        source_kind="summary",
        importance=0.4,
        score=score,
        score_breakdown={"lexical": lexical, "recency": recency},
        origin=SimpleNamespace(
            scope_key=f"session:{item_id}",
            scope_type="session_summary",
            session_id="session-origin",
            root_session_id="session-origin",
            matched_scopes=["agent", "user"],
        ),
        override=SimpleNamespace(status="none", target_id=None),
    )


def test_memory_search_returns_lexical_hits_across_memory_and_session_summaries(
    test_client: TestClient,
) -> None:
    session_record = _create_session(test_client, "Lexical Search")

    body_entry = _insert_memory_entry(
        body="banana launch protocol",
        summary="fallback",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
    )
    summary_entry = _insert_memory_entry(
        body="unrelated",
        summary="banana briefing note",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
    )
    session_summary = _insert_session_summary(
        summary="banana retrospective",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
    )

    response = test_client.get(
        "/memory/search",
        params={"q": "banana", "session_id": session_record["id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    by_id = {item["id"]: item for item in payload["items"]}

    assert body_entry.id in by_id
    assert summary_entry.id in by_id
    assert session_summary.id in by_id
    assert by_id[body_entry.id]["record_type"] == "memory_entry"
    assert by_id[body_entry.id]["body"] == "banana launch protocol"
    assert by_id[summary_entry.id]["summary"] == "banana briefing note"
    assert by_id[session_summary.id]["record_type"] == "session_summary"
    assert by_id[session_summary.id]["body"] is None


def test_memory_search_prioritizes_manual_memory_over_automatic(test_client: TestClient) -> None:
    session_record = _create_session(test_client, "Manual Priority")

    automatic = _insert_memory_entry(
        body="orchid dossier",
        source_kind="autosaved",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
    )
    manual = _insert_memory_entry(
        body="orchid dossier",
        source_kind="manual",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
    )

    response = test_client.get(
        "/memory/search",
        params={"q": "orchid", "session_id": session_record["id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["id"] == manual.id
    assert payload["items"][0]["source_kind"] == "manual"
    assert {item["id"] for item in payload["items"][:2]} == {manual.id, automatic.id}
    assert payload["items"][0]["score"] > payload["items"][1]["score"]


def test_memory_search_excludes_hidden_and_soft_deleted_entries(test_client: TestClient) -> None:
    session_record = _create_session(test_client, "Hidden Exclusion")

    _insert_memory_entry(
        body="ghost phrase",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
        hidden_from_recall=True,
    )
    _insert_memory_entry(
        body="ghost phrase",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
        deleted_at=utc_now(),
    )

    response = test_client.get(
        "/memory/search",
        params={"q": "ghost", "session_id": session_record["id"]},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_memory_recall_preview_substitutes_automatic_entries_with_manual_override_and_logs(
    test_client: TestClient,
) -> None:
    session_record = _create_session(test_client, "Override Recall")

    automatic = _insert_memory_entry(
        body="pineapple incident report",
        summary="base",
        source_kind="autosaved",
        importance=0.2,
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
    )
    manual = _insert_memory_entry(
        body="Operator correction",
        summary="manual replacement",
        source_kind="manual",
        importance=0.2,
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
        override_target_entry_id=automatic.id,
    )

    response = test_client.get(
        "/memory/recall/preview",
        params={
            "q": "pineapple",
            "session_id": session_record["id"],
            "run_id": "run-123",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == [manual.id]
    item = payload["items"][0]
    assert item["source_kind"] == "manual"
    assert item["override"]["status"] == "overrides_automatic"
    assert item["override"]["target_id"] == automatic.id
    assert item["override"]["selected_via_substitution"] is True

    with get_db_session() as session:
        rows = list(
            session.exec(select(MemoryRecallLog).order_by(MemoryRecallLog.created_at.asc()))
        )

    assert len(rows) == 1
    assert rows[0].query_text == "pineapple"
    assert rows[0].run_id == "run-123"
    assert rows[0].record_type == "memory_entry"
    assert rows[0].record_id == manual.id
    assert rows[0].source_kind == "manual"
    assert rows[0].override_status == "overrides_automatic"
    assert json.loads(rows[0].reason_json)["substituted_for_id"] == automatic.id


def test_hidden_manual_override_suppresses_automatic_base_from_recall(
    test_client: TestClient,
) -> None:
    session_record = _create_session(test_client, "Hidden Override")

    automatic = _insert_memory_entry(
        body="papaya notebook",
        source_kind="autosaved",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
    )
    _insert_memory_entry(
        body="suppressed correction",
        source_kind="manual",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
        override_target_entry_id=automatic.id,
        hidden_from_recall=True,
    )

    response = test_client.get(
        "/memory/recall/preview",
        params={"q": "papaya", "session_id": session_record["id"]},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_memory_search_respects_scope_filters_and_defaults(test_client: TestClient) -> None:
    workspace_root = _workspace_root(test_client)
    agent_id = _default_agent_id()
    current = _create_session(test_client, "Current Root")
    _create_session(test_client, "Other Root")

    with get_db_session() as session:
        child = SessionRecord(
            agent_id=agent_id,
            kind="subagent",
            parent_session_id=current["id"],
            root_session_id=current["id"],
            spawn_depth=1,
            title="Tree Child",
            status="active",
            started_at=utc_now(),
        )
        session.add(child)
        session.commit()
        session.refresh(child)

    conversation_entry = _insert_memory_entry(
        body="scope probe",
        session_id=current["id"],
        root_session_id=current["id"],
    )
    tree_entry = _insert_memory_entry(
        body="scope probe",
        session_id=child.id,
        root_session_id=current["id"],
    )
    agent_entry = _insert_memory_entry(body="scope probe", agent_id=agent_id)
    user_entry = _insert_memory_entry(body="scope probe", user_scope_key="local-user")
    workspace_entry = _insert_memory_entry(body="scope probe", workspace_path=workspace_root)

    default_with_session = test_client.get(
        "/memory/search",
        params={"q": "scope", "session_id": current["id"]},
    )
    default_without_session = test_client.get("/memory/search", params={"q": "scope"})
    conversation_only = test_client.get(
        "/memory/search",
        params={
            "q": "scope",
            "session_id": current["id"],
            "scope": "current_conversation",
        },
    )
    tree_only = test_client.get(
        "/memory/search",
        params={
            "q": "scope",
            "session_id": current["id"],
            "scope": "current_session_tree",
        },
    )
    agent_only = test_client.get(
        "/memory/search",
        params={"q": "scope", "scope": "agent"},
    )
    user_only = test_client.get(
        "/memory/search",
        params={"q": "scope", "scope": "user"},
    )
    workspace_only = test_client.get(
        "/memory/search",
        params={"q": "scope", "scope": "workspace"},
    )

    assert default_with_session.status_code == 200
    assert default_without_session.status_code == 200
    assert conversation_only.status_code == 200
    assert tree_only.status_code == 200
    assert agent_only.status_code == 200
    assert user_only.status_code == 200
    assert workspace_only.status_code == 200

    assert {item["id"] for item in default_with_session.json()["items"]} == {
        conversation_entry.id,
        tree_entry.id,
        agent_entry.id,
        user_entry.id,
        workspace_entry.id,
    }
    assert {item["id"] for item in default_without_session.json()["items"]} == {
        agent_entry.id,
        user_entry.id,
        workspace_entry.id,
    }
    assert {item["id"] for item in conversation_only.json()["items"]} == {conversation_entry.id}
    assert {item["id"] for item in tree_only.json()["items"]} == {
        conversation_entry.id,
        tree_entry.id,
    }
    assert {item["id"] for item in agent_only.json()["items"]} == {agent_entry.id}
    assert {item["id"] for item in user_only.json()["items"]} == {user_entry.id}
    assert {item["id"] for item in workspace_only.json()["items"]} == {workspace_entry.id}


def test_memory_scopes_endpoint_reports_context_and_defaults(test_client: TestClient) -> None:
    session_record = _create_session(test_client, "Scopes Context")

    with_session = test_client.get(
        "/memory/scopes",
        params={"session_id": session_record["id"]},
    )
    without_session = test_client.get("/memory/scopes")

    assert with_session.status_code == 200
    with_payload = with_session.json()
    assert with_payload["context"]["session_id"] == session_record["id"]
    assert with_payload["context"]["root_session_id"] == session_record["root_session_id"]
    assert with_payload["default_scopes"] == [
        "current_conversation",
        "current_session_tree",
        "agent",
        "user",
        "workspace",
    ]
    with_supported = {item["name"]: item for item in with_payload["supported_scopes"]}
    assert with_supported["current_conversation"]["available"] is True
    assert with_supported["current_session_tree"]["available"] is True

    assert without_session.status_code == 200
    without_payload = without_session.json()
    assert without_payload["default_scopes"] == ["agent", "user", "workspace"]
    without_supported = {item["name"]: item for item in without_payload["supported_scopes"]}
    assert without_supported["current_conversation"]["available"] is False
    assert without_supported["current_session_tree"]["available"] is False


def test_memory_endpoints_validate_scope_context_requirements(test_client: TestClient) -> None:
    search_response = test_client.get(
        "/memory/search",
        params={"q": "banana", "scope": "current_conversation"},
    )
    preview_response = test_client.get(
        "/memory/recall/preview",
        params={"q": "banana", "scope": "current_session_tree"},
    )
    missing_session_response = test_client.get(
        "/memory/scopes",
        params={"session_id": "missing-session"},
    )

    assert search_response.status_code == 400
    assert "session_id" in search_response.json()["detail"]
    assert preview_response.status_code == 400
    assert "session_id" in preview_response.json()["detail"]
    assert missing_session_response.status_code == 404


def test_current_conversation_scope_excludes_memories_from_previous_conversation_after_reset(
    test_client: TestClient,
) -> None:
    session_record = _create_session(test_client, "Conversation Reset Search")
    original_conversation_id = session_record["conversation_id"]

    old_entry = _insert_memory_entry(
        body="reset scope probe",
        title="old-conversation-memory",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
        conversation_id=original_conversation_id,
    )

    reset_response = test_client.post(f"/sessions/{session_record['id']}/reset")
    assert reset_response.status_code == 200
    updated_session = reset_response.json()

    new_entry = _insert_memory_entry(
        body="reset scope probe",
        title="new-conversation-memory",
        session_id=session_record["id"],
        root_session_id=session_record["root_session_id"],
        conversation_id=updated_session["conversation_id"],
    )

    conversation_only = test_client.get(
        "/memory/search",
        params={
            "q": "reset scope",
            "session_id": session_record["id"],
            "scope": "current_conversation",
        },
    )
    tree_only = test_client.get(
        "/memory/search",
        params={
            "q": "reset scope",
            "session_id": session_record["id"],
            "scope": "current_session_tree",
        },
    )

    assert conversation_only.status_code == 200
    assert tree_only.status_code == 200
    assert {item["id"] for item in conversation_only.json()["items"]} == {new_entry.id}
    assert {item["id"] for item in tree_only.json()["items"]} == {
        old_entry.id,
        new_entry.id,
    }


def test_select_for_recall_returns_empty_when_memory_v1_disabled(test_client: TestClient) -> None:
    _set_feature_flag("memory_v1_enabled", False)
    session_record = _create_session(test_client, "Recall Flag Off")

    with get_db_session() as session:
        service = MemoryService(session)

        def _unexpected_search(**_kwargs):
            raise AssertionError("Runtime recall search should not run when feature is disabled.")

        service.search.search = _unexpected_search  # type: ignore[assignment]
        candidates = service.select_for_recall(
            input_text="any recall input",
            session_id=session_record["id"],
        )

    assert candidates == []


def test_select_for_recall_applies_runtime_quality_filters_and_temporal_dedupe(
    test_client: TestClient,
) -> None:
    _set_feature_flag("memory_v1_enabled", True)
    session_record = _create_session(test_client, "Recall Filtering")

    with get_db_session() as session:
        recent_duplicate = MemoryRecallLog(
            memory_id="dup-1",
            scope_type="session_summary",
            scope_key="session:dup-1",
            session_id=session_record["id"],
            conversation_id=session_record["conversation_id"],
            recall_reason="runtime_context",
            decision="included",
            record_type="session_summary",
            record_id="dup-1",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        old_duplicate = MemoryRecallLog(
            memory_id="stale-dup",
            scope_type="session_summary",
            scope_key="session:stale-dup",
            session_id=session_record["id"],
            conversation_id=session_record["conversation_id"],
            recall_reason="runtime_context",
            decision="included",
            record_type="session_summary",
            record_id="stale-dup",
            created_at=utc_now() - timedelta(hours=13),
            updated_at=utc_now() - timedelta(hours=13),
        )
        session.add(recent_duplicate)
        session.add(old_duplicate)
        session.commit()

        service = MemoryService(session)
        mocked_items = [
            _make_search_item(item_id="keep-1", lexical=1.2, recency=0.6, score=2.1),
            _make_search_item(item_id="lexical-zero", lexical=0.0, recency=0.6, score=2.0),
            _make_search_item(item_id="old-1", lexical=0.8, recency=0.0, score=1.9),
            _make_search_item(item_id="dup-1", lexical=0.9, recency=0.6, score=1.8),
            _make_search_item(item_id="stale-dup", lexical=0.7, recency=0.6, score=1.7),
        ]
        service.search.search = lambda **_kwargs: SimpleNamespace(items=mocked_items)  # type: ignore[assignment]

        candidates = service.select_for_recall(
            input_text="runtime recall query",
            session_id=session_record["id"],
            limit=5,
        )

    assert [candidate.item.id for candidate in candidates] == ["keep-1", "old-1", "stale-dup"]


def test_runtime_recall_event_persists_query_text(test_client: TestClient) -> None:
    _set_feature_flag("memory_v1_enabled", True)
    session_record = _create_session(test_client, "Recall Query Persistence")

    with get_db_session() as session:
        repository = AgentExecutionRepository(session)
        assistant = repository.create_message(
            session_record["id"],
            "assistant",
            "Assistant response with runtime recall.",
        )
        session.commit()

        service = MemoryService(session)
        service.record_recall_event(
            assistant_message_id=assistant.id,
            session_id=session_record["id"],
            task_run_id="task-run-1",
            payload={
                "reason_summary": "1 memory item(s) injected for recall.",
                "query_text": "  repositories github check  ",
                "items": [
                    {
                        "memory_id": "runtime-memory-id",
                        "title": "Runtime Summary",
                        "kind": "session_summary",
                        "scope": f"session:{session_record['id']}",
                        "source_kind": "summary",
                        "source_label": "Summary",
                        "importance": "medium",
                        "reason": "Matched current session",
                    }
                ],
            },
        )

        row = session.exec(
            select(MemoryRecallLog)
            .where(MemoryRecallLog.assistant_message_id == assistant.id)
            .order_by(MemoryRecallLog.created_at.desc())
        ).first()

    assert row is not None
    assert row.query_text == "repositories github check"


def test_batch_get_items_chunks_large_in_queries() -> None:
    with get_db_session() as session:
        service = MemoryService(session)
        lookup_ids = [f"memory-{index}" for index in range(501)]
        max_bind_params = 200
        observed_chunk_sizes: list[int] = []

        def _exec_with_bind_guard(statement, *args, **kwargs):
            criteria = list(getattr(statement, "_where_criteria", ()))
            if criteria:
                right = getattr(criteria[0], "right", None)
                values = getattr(right, "value", None)
                if isinstance(values, list):
                    observed_chunk_sizes.append(len(values))
                    if len(values) > max_bind_params:
                        raise AssertionError(
                            f"Query used {len(values)} bind params; expected <= {max_bind_params}"
                        )
            return []

        session.exec = _exec_with_bind_guard  # type: ignore[assignment]

        items = service._batch_get_items(lookup_ids)

    assert items == {}
    assert observed_chunk_sizes
