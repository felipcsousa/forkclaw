from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import select

from app.db.session import get_db_session
from app.models.entities import Agent, MemoryEntry, Setting


def _default_agent_id() -> str:
    with get_db_session() as session:
        agent = session.exec(select(Agent).where(Agent.is_default.is_(True))).one()
    return agent.id


def _set_feature_flag(key: str, enabled: bool) -> None:
    with get_db_session() as session:
        setting = session.exec(
            select(Setting).where(Setting.scope == "features", Setting.key == key)
        ).one()
        setting.value_text = "true" if enabled else "false"
        session.add(setting)
        session.commit()


def _enable_memory_v1(*, manual_crud: bool = True, hard_delete: bool = False) -> None:
    _set_feature_flag("memory_v1_enabled", True)
    _set_feature_flag("memory_manual_crud_enabled", manual_crud)
    _set_feature_flag("memory_hard_delete_enabled", hard_delete)


def _seed_memory(
    *,
    kind: str = "stable",
    title: str,
    content: str,
    scope: str = "global",
    source_kind: str = "manual",
    source_label: str | None = None,
    importance: str = "medium",
    state: str = "active",
    recall_status: str = "active",
    is_manual: bool | None = None,
    is_override: bool = False,
    origin_session_id: str | None = None,
    origin_subagent_session_id: str | None = None,
    original_memory_id: str | None = None,
) -> str:
    agent_id = _default_agent_id()
    resolved_source_kind = "autosaved" if source_kind == "automatic" else source_kind
    scope_key = f"user/{scope.lower()}"
    record = MemoryEntry(
        agent_id=agent_id,
        scope_type="stable" if kind == "stable" else "episodic",
        scope_key=scope_key,
        session_id=origin_session_id,
        root_session_id=origin_session_id,
        parent_session_id=origin_subagent_session_id,
        source_kind=resolved_source_kind,
        lifecycle_state="soft_deleted" if state == "deleted" else "active",
        title=title,
        body=content,
        summary=content[:120],
        importance={"low": 0.2, "medium": 0.5, "high": 0.9}[importance],
        confidence=1.0,
        dedupe_hash=f"seed-{uuid4().hex}",
        created_by="user" if resolved_source_kind == "manual" else "system",
        updated_by="user" if resolved_source_kind == "manual" else "system",
        user_scope_key="local-user" if resolved_source_kind == "manual" else None,
        redaction_state="clean",
        security_state="safe",
        hidden_from_recall=recall_status == "hidden",
        deleted_at=None,
        override_target_entry_id=original_memory_id if is_override else None,
    )
    if state != "active":
        from app.models.entities import utc_now

        record.deleted_at = utc_now()
    with get_db_session() as session:
        session.add(record)
        session.commit()
        session.refresh(record)
    return record.id


def test_memory_items_can_be_created_filtered_and_audited(test_client: TestClient) -> None:
    _enable_memory_v1(manual_crud=True, hard_delete=True)

    create_response = test_client.post(
        "/memory/items",
        json={
            "kind": "stable",
            "title": "Travel preferences",
            "content": "Prefers aisle seats and morning departures.",
            "scope": "profile",
            "importance": "high",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["kind"] == "stable"
    assert created["source_kind"] == "manual"
    assert created["source_label"] == "Manual"
    assert created["state"] == "active"
    assert created["recall_status"] == "active"
    assert created["is_manual"] is True
    assert created["is_override"] is False

    list_response = test_client.get(
        "/memory/items",
        params={
            "kind": "stable",
            "query": "aisle",
            "scope": "profile",
            "state": "active",
            "mode": "manual",
        },
    )

    assert list_response.status_code == 200
    listed = list_response.json()["items"]
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]

    update_response = test_client.put(
        f"/memory/items/{created['id']}",
        json={
            "title": "Flight preferences",
            "content": "Prefers aisle seats, morning departures, and short layovers.",
            "importance": "medium",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "Flight preferences"
    assert updated["importance"] == "medium"

    hide_response = test_client.post(f"/memory/items/{created['id']}/hide")
    assert hide_response.status_code == 200
    assert hide_response.json()["recall_status"] == "hidden"

    hidden_list_response = test_client.get(
        "/memory/items",
        params={"state": "active", "recall_status": "hidden"},
    )
    assert hidden_list_response.status_code == 200
    assert hidden_list_response.json()["items"][0]["id"] == created["id"]

    restore_response = test_client.post(f"/memory/items/{created['id']}/restore")
    assert restore_response.status_code == 200
    assert restore_response.json()["recall_status"] == "active"

    soft_delete_response = test_client.delete(f"/memory/items/{created['id']}")
    assert soft_delete_response.status_code == 200
    assert soft_delete_response.json()["state"] == "deleted"

    history_response = test_client.get(f"/memory/items/{created['id']}/history")
    assert history_response.status_code == 200
    history_actions = [entry["action"] for entry in history_response.json()["items"]]
    assert history_actions[:5] == [
        "created",
        "updated",
        "hidden",
        "restored",
        "soft_deleted",
    ]

    hard_delete_response = test_client.delete(
        f"/memory/items/{created['id']}",
        params={"hard": "true"},
    )
    assert hard_delete_response.status_code == 204

    detail_after_hard_delete = test_client.get(f"/memory/items/{created['id']}")
    assert detail_after_hard_delete.status_code == 404


def test_updating_autosaved_memory_creates_manual_override_without_mutating_original(
    test_client: TestClient,
) -> None:
    original_id = _seed_memory(
        kind="episodic",
        title="Launch retrospective",
        content="Autosaved note about launch blockers.",
        scope="workspace",
        source_kind="autosaved",
        source_label="Session capture",
        importance="medium",
        recall_status="active",
        is_manual=False,
    )

    update_response = test_client.put(
        f"/memory/items/{original_id}",
        json={
            "title": "Launch retrospective override",
            "content": "Manual correction: blocker was the release checklist.",
            "importance": "high",
        },
    )

    assert update_response.status_code == 200
    override = update_response.json()
    assert override["id"] != original_id
    assert override["source_kind"] == "manual"
    assert override["source_label"] == "Manual override"
    assert override["is_override"] is True
    assert override["is_manual"] is True
    assert override["original_memory_id"] == original_id

    original_response = test_client.get(f"/memory/items/{original_id}")
    assert original_response.status_code == 200
    original = original_response.json()
    assert original["title"] == "Launch retrospective"
    assert original["content"] == "Autosaved note about launch blockers."
    assert original["recall_status"] == "hidden"
    assert original["source_kind"] == "autosaved"

    list_response = test_client.get(
        "/memory/items",
        params={"query": "launch", "scope": "workspace"},
    )
    assert list_response.status_code == 200
    ids = {item["id"] for item in list_response.json()["items"]}
    assert {original_id, override["id"]} <= ids

    history_response = test_client.get(f"/memory/items/{original_id}/history")
    assert history_response.status_code == 200
    assert history_response.json()["items"][-1]["action"] == "override_created"


def test_recall_endpoints_surface_memories_used_for_assistant_responses(
    test_client: TestClient,
) -> None:
    _enable_memory_v1()

    memory_id = _seed_memory(
        kind="stable",
        title="Tea preference",
        content="The user prefers oolong tea in the afternoon.",
        scope="profile",
        source_kind="manual",
        importance="high",
    )

    execute_response = test_client.post(
        "/agent/execute",
        json={"title": "Recall demo", "message": "Please use the oolong tea preference."},
    )

    assert execute_response.status_code == 201
    execution = execute_response.json()

    recall_detail_response = test_client.get(
        f"/memory/recall/messages/{execution['assistant_message_id']}"
    )
    assert recall_detail_response.status_code == 200
    recall_detail = recall_detail_response.json()
    assert recall_detail["assistant_message_id"] == execution["assistant_message_id"]
    assert recall_detail["session_id"] == execution["session_id"]
    assert recall_detail["items"][0]["memory_id"] == memory_id
    assert recall_detail["items"][0]["title"] == "Tea preference"
    assert "oolong" in recall_detail["items"][0]["reason"].lower()

    session_recalls_response = test_client.get(f"/memory/recall/sessions/{execution['session_id']}")
    assert session_recalls_response.status_code == 200
    session_recalls = session_recalls_response.json()["items"]
    assert session_recalls[0]["assistant_message_id"] == execution["assistant_message_id"]
    assert session_recalls[0]["recalled_count"] == 1

    recall_log_response = test_client.get("/memory/recall")
    assert recall_log_response.status_code == 200
    recall_log = recall_log_response.json()["items"]
    assert recall_log[0]["assistant_message_id"] == execution["assistant_message_id"]
    assert recall_log[0]["items"][0]["memory_id"] == memory_id


def test_hidden_memories_are_excluded_from_recall(test_client: TestClient) -> None:
    _enable_memory_v1()

    memory_id = _seed_memory(
        kind="stable",
        title="Secret preference",
        content="The user prefers jasmine rice.",
        scope="profile",
        source_kind="manual",
        importance="high",
        recall_status="hidden",
    )

    execute_response = test_client.post(
        "/agent/execute",
        json={"title": "Hidden recall", "message": "Remember the jasmine rice detail."},
    )

    assert execute_response.status_code == 201
    execution = execute_response.json()

    recall_detail_response = test_client.get(
        f"/memory/recall/messages/{execution['assistant_message_id']}"
    )
    assert recall_detail_response.status_code == 200
    recall_detail = recall_detail_response.json()
    assert recall_detail["items"] == []

    recall_log_response = test_client.get("/memory/recall")
    assert recall_log_response.status_code == 200
    if recall_log_response.json()["items"]:
        recalled_ids = {
            item["memory_id"]
            for event in recall_log_response.json()["items"]
            for item in event["items"]
        }
        assert memory_id not in recalled_ids


def test_recall_history_survives_hard_deleted_memory(test_client: TestClient) -> None:
    _enable_memory_v1(manual_crud=True, hard_delete=True)
    memory_id = _seed_memory(
        kind="stable",
        title="Tea preference",
        content="The user prefers oolong tea in the afternoon.",
        scope="profile",
        source_kind="manual",
        importance="high",
    )

    execute_response = test_client.post(
        "/agent/execute",
        json={"title": "Hard delete recall", "message": "Please use the oolong tea preference."},
    )

    assert execute_response.status_code == 201
    execution = execute_response.json()

    hard_delete_response = test_client.delete(
        f"/memory/items/{memory_id}",
        params={"hard": "true"},
    )
    assert hard_delete_response.status_code == 204

    recall_detail_response = test_client.get(
        f"/memory/recall/messages/{execution['assistant_message_id']}"
    )
    session_recalls_response = test_client.get(f"/memory/recall/sessions/{execution['session_id']}")
    recall_log_response = test_client.get("/memory/recall")

    assert recall_detail_response.status_code == 200
    assert session_recalls_response.status_code == 200
    assert recall_log_response.status_code == 200

    recall_detail = recall_detail_response.json()
    assert recall_detail["items"][0]["memory_id"] == memory_id
    assert recall_detail["items"][0]["title"] == "Deleted memory"
    assert recall_detail["items"][0]["source_kind"] == "manual"
    assert recall_detail["items"][0]["scope"] == "profile"

    session_recall = session_recalls_response.json()["items"][0]
    assert session_recall["items"][0]["memory_id"] == memory_id
    assert session_recall["items"][0]["title"] == "Deleted memory"

    recall_log = recall_log_response.json()["items"][0]
    assert recall_log["items"][0]["memory_id"] == memory_id
    assert recall_log["items"][0]["title"] == "Deleted memory"


def test_delete_memory_item_endpoint(test_client: TestClient) -> None:
    _enable_memory_v1(manual_crud=True, hard_delete=True)

    create_response = test_client.post(
        "/memory/items",
        json={
            "kind": "stable",
            "title": "Travel preferences",
            "content": "Prefers aisle seats and morning departures.",
            "scope": "profile",
            "importance": "high",
        },
    )

    created = create_response.json()
    item_id = created["id"]

    del_res_soft = test_client.delete(f"/memory/items/{item_id}")
    assert del_res_soft.status_code == 200

    del_res_hard = test_client.delete(f"/memory/items/{item_id}?hard=true")
    assert del_res_hard.status_code == 204


def test_memory_items_can_be_promoted_and_demoted(test_client: TestClient) -> None:
    _enable_memory_v1(manual_crud=True, hard_delete=True)

    create_response = test_client.post(
        "/memory/items",
        json={
            "kind": "stable",
            "title": "Promote demote preference",
            "content": "A preference to test importance changes.",
            "scope": "profile",
            "importance": "medium",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["importance"] == "medium"

    demote_response = test_client.post(f"/memory/items/{created['id']}/demote")
    assert demote_response.status_code == 200
    assert demote_response.json()["kind"] == "episodic"

    promote_response = test_client.post(f"/memory/items/{created['id']}/promote")
    assert promote_response.status_code == 200
    assert promote_response.json()["kind"] == "stable"
