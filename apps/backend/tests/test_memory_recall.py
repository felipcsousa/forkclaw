from __future__ import annotations

import json
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import select

from app.db.session import get_db_session
from app.models.entities import (
    Agent,
    MemoryEntry,
    MemoryRecallLog,
    SessionRecord,
    SessionSummary,
    utc_now,
)


def _default_agent_id() -> str:
    with get_db_session() as session:
        agent = session.exec(select(Agent).where(Agent.is_default.is_(True))).one()
    return agent.id


def _workspace_root(test_client: TestClient) -> str:
    response = test_client.get("/settings/operational")
    assert response.status_code == 200
    return response.json()["workspace_root"]


def _create_session(test_client: TestClient, title: str) -> dict:
    response = test_client.post("/sessions", json={"title": title})
    assert response.status_code == 201
    return response.json()


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
) -> MemoryEntry:
    with get_db_session() as session:
        normalized_source = "autosaved" if source_kind == "automatic" else source_kind
        resolved_scope_type = "episodic" if session_id is not None else "stable"
        resolved_scope_key = (
            f"session:{session_id}"
            if session_id is not None
            else (
                f"agent:{agent_id}"
                if agent_id is not None
                else (
                    f"user/{user_scope_key}"
                    if user_scope_key is not None
                    else (
                        f"workspace:{workspace_path}"
                        if workspace_path is not None
                        else "agent:default"
                    )
                )
            )
        )
        entry = MemoryEntry(
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
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


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
) -> SessionSummary:
    with get_db_session() as session:
        normalized_source = "summary" if source_kind == "automatic" else source_kind
        item = SessionSummary(
            scope_key=f"session:{session_id or uuid4().hex}",
            summary_text=summary,
            source_kind=normalized_source,
            importance=importance,
            agent_id=agent_id,
            session_id=session_id,
            root_session_id=root_session_id,
            created_by="user" if normalized_source == "manual" else "system",
            workspace_path=workspace_path,
            user_scope_key=user_scope_key,
            hidden_from_recall=hidden_from_recall,
            deleted_at=deleted_at,
            override_target_summary_id=override_target_summary_id,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


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
