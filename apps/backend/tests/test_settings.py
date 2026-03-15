from __future__ import annotations

from fastapi.testclient import TestClient

from app.schemas.settings import SettingsListResponse


def test_list_settings(test_client: TestClient) -> None:
    response = test_client.get("/settings")

    assert response.status_code == 200

    # Assert that it matches the schema
    data = response.json()
    validated = SettingsListResponse.model_validate(data)

    # Also assert that there's at least one setting
    assert len(validated.items) > 0

    # Do some spot checks like in test_agent_os_endpoints
    keys = {(item.scope, item.key) for item in validated.items}
    assert ("app", "default_agent_slug") in keys
    assert ("app", "timezone") in keys
    assert ("security", "approval_mode") in keys
