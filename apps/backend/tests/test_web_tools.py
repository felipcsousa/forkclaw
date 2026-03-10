from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.db.session import get_db_session
from app.models.entities import ToolCall
from app.tools.web.fetch import extract_readable_content, validate_public_web_url
from app.tools.web.providers.base import SearchProviderResponse, SearchResultItem
from app.tools.web.providers.brave import BraveWebSearchProvider


def test_validate_public_web_url_rejects_private_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_getaddrinfo(*args, **kwargs):
        del args, kwargs
        return [(0, 0, 0, "", ("127.0.0.1", 80))]

    monkeypatch.setattr("app.tools.web.fetch.socket.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError) as exc_info:
        validate_public_web_url("http://localhost:8000/demo")

    assert "public host" in str(exc_info.value)


def test_extract_readable_content_supports_markdown_and_truncation() -> None:
    html = """
    <html>
      <head><title>Example article</title></head>
      <body>
        <main>
          <h1>Example article</h1>
          <p>This is the first paragraph.</p>
          <p>This is the second paragraph with more content.</p>
        </main>
      </body>
    </html>
    """

    payload = extract_readable_content(
        html=html,
        url="https://example.com/article",
        extract_mode="markdown",
        max_chars=48,
    )

    assert payload["content"].startswith("# Example article")
    assert payload["extract_mode"] == "markdown"
    assert payload["truncated"] is True
    assert len(payload["content"]) == 48


def test_agent_can_use_web_search_with_cache(
    test_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update_response = test_client.put("/tools/policy", json={"profile_id": "research"})
    assert update_response.status_code == 200

    provider_calls: list[tuple[str, int]] = []

    def fake_search(self, query: str, count: int) -> SearchProviderResponse:
        del self
        provider_calls.append((query, count))
        return SearchProviderResponse(
            provider="brave",
            query=query,
            results=[
                SearchResultItem(
                    title="Nanobot Docs",
                    url="https://docs.example.com/nanobot",
                    snippet="Canonical docs result.",
                ),
                SearchResultItem(
                    title="Nanobot Repo",
                    url="https://github.com/example/nanobot",
                    snippet="Source repository result.",
                ),
            ],
        )

    monkeypatch.setenv("BRAVE_API_KEY", "test-brave-key")
    monkeypatch.setattr(BraveWebSearchProvider, "search", fake_search)

    first_response = test_client.post(
        "/agent/execute",
        json={"message": "tool:web_search query='nanobot' count=2"},
    )
    assert first_response.status_code == 201
    first_payload = first_response.json()
    assert first_payload["status"] == "completed"
    assert "Nanobot Docs" in first_payload["output_text"]
    assert "web_search" in first_payload["tools_used"]

    second_response = test_client.post(
        "/agent/execute",
        json={"message": "tool:web_search query='nanobot' count=2"},
    )
    assert second_response.status_code == 201
    assert len(provider_calls) == 1

    with get_db_session() as session:
        tool_calls = list(
            session.exec(
                select(ToolCall)
                .where(ToolCall.tool_name == "web_search")
                .order_by(ToolCall.created_at.asc())
            )
        )

    first_output = json.loads(tool_calls[0].output_json or "{}")
    second_output = json.loads(tool_calls[1].output_json or "{}")
    assert first_output["data"]["cached"] is False
    assert second_output["data"]["cached"] is True


def test_agent_can_use_web_fetch_with_cache(
    test_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update_response = test_client.put("/tools/policy", json={"profile_id": "research"})
    assert update_response.status_code == 200

    fetch_calls: list[tuple[str, str, int]] = []

    def fake_fetch_web_document(
        *,
        url: str,
        extract_mode: str,
        max_chars: int,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> dict[str, object]:
        del timeout_seconds, max_response_bytes
        fetch_calls.append((url, extract_mode, max_chars))
        return {
            "url": url,
            "final_url": url,
            "title": "Example article",
            "extract_mode": extract_mode,
            "content": "# Example article\n\nBody paragraph from the web.",
            "truncated": False,
        }

    monkeypatch.setattr("app.tools.registry.fetch_web_document", fake_fetch_web_document)

    first_response = test_client.post(
        "/agent/execute",
        json={
            "message": (
                "tool:web_fetch url='https://example.com/article' "
                "extract_mode=markdown max_chars=120"
            )
        },
    )
    assert first_response.status_code == 201
    first_payload = first_response.json()
    assert first_payload["status"] == "completed"
    assert "Example article" in first_payload["output_text"]
    assert "web_fetch" in first_payload["tools_used"]

    second_response = test_client.post(
        "/agent/execute",
        json={
            "message": (
                "tool:web_fetch url='https://example.com/article' "
                "extract_mode=markdown max_chars=120"
            )
        },
    )
    assert second_response.status_code == 201
    assert len(fetch_calls) == 1

    with get_db_session() as session:
        tool_calls = list(
            session.exec(
                select(ToolCall)
                .where(ToolCall.tool_name == "web_fetch")
                .order_by(ToolCall.created_at.asc())
            )
        )

    first_output = json.loads(tool_calls[0].output_json or "{}")
    second_output = json.loads(tool_calls[1].output_json or "{}")
    assert first_output["data"]["cached"] is False
    assert second_output["data"]["cached"] is True


def test_web_search_requires_brave_api_key(
    test_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update_response = test_client.put("/tools/policy", json={"profile_id": "research"})
    assert update_response.status_code == 200

    monkeypatch.delenv("BRAVE_API_KEY", raising=False)

    execute_response = test_client.post(
        "/agent/execute",
        json={"message": "tool:web_search query='nanobot' count=2"},
    )
    assert execute_response.status_code == 201
    payload = execute_response.json()

    assert payload["status"] == "failed"
    assert "BRAVE_API_KEY" in payload["output_text"]

    with get_db_session() as session:
        tool_call = session.exec(
            select(ToolCall)
            .where(ToolCall.tool_name == "web_search")
            .order_by(ToolCall.created_at.desc())
        ).one()

    assert tool_call.status == "failed"
