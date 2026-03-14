from __future__ import annotations

from sqlalchemy import inspect

from app.db.session import get_engine


def test_memory_v1_canonical_tables_exist(test_client) -> None:
    del test_client
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())

    assert {
        "memory_entries",
        "memory_relations",
        "memory_recall_log",
        "session_summaries",
        "memory_change_log",
    } <= tables


def test_session_create_and_reset_expose_conversation_id(test_client) -> None:
    create_response = test_client.post("/sessions", json={"title": "Memory Session"})

    assert create_response.status_code == 201
    created_session = create_response.json()
    assert created_session["conversation_id"]

    reset_response = test_client.post(f"/sessions/{created_session['id']}/reset")

    assert reset_response.status_code == 200
    reset_session = reset_response.json()
    assert reset_session["conversation_id"]
    assert reset_session["conversation_id"] != created_session["conversation_id"]


def test_memory_public_routes_are_registered(test_client) -> None:
    endpoints = [
        "/memory/entries",
        "/memory/scopes",
        "/memory/search?q=memory",
        "/memory/recall/preview?q=memory",
        "/memory/items",
        "/memory/recall",
    ]

    for path in endpoints:
        response = test_client.get(path)
        assert not (response.status_code == 404 and response.json().get("detail") == "Not Found"), (
            path
        )
