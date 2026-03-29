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

def test_get_operational_settings_success(test_client: TestClient) -> None:
    response = test_client.get("/settings/operational")
    assert response.status_code == 200
    data = response.json()
    assert "provider" in data

def test_get_operational_settings_value_error(test_client: TestClient, monkeypatch) -> None:
    def mock_get(*args, **kwargs):
        raise ValueError("simulated value error")
    monkeypatch.setattr("app.services.operational_settings.OperationalSettingsService.get_operational_settings", mock_get)
    response = test_client.get("/settings/operational")
    assert response.status_code == 400
    assert "simulated value error" in response.json()["detail"]

def test_get_operational_settings_secret_store_error(test_client: TestClient, monkeypatch) -> None:
    from app.core.secrets import SecretStoreError
    def mock_get(*args, **kwargs):
        raise SecretStoreError("simulated secret error")
    monkeypatch.setattr("app.services.operational_settings.OperationalSettingsService.get_operational_settings", mock_get)
    response = test_client.get("/settings/operational")
    assert response.status_code == 503
    assert "simulated secret error" in response.json()["detail"]

def test_update_operational_settings_success(test_client: TestClient) -> None:
    payload = {
        "provider": "openai",
        "model_name": "gpt-4",
        "workspace_root": "/",
        "max_iterations_per_execution": 5,
        "daily_budget_usd": 10.0,
        "monthly_budget_usd": 100.0,
        "default_view": "chat",
        "activity_poll_seconds": 5,
        "heartbeat_interval_seconds": 60,
        "provider_keys": {"openai": "test-key"}
    }
    response = test_client.put("/settings/operational", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"

def test_update_operational_settings_value_error(test_client: TestClient, monkeypatch) -> None:
    def mock_update(*args, **kwargs):
        raise ValueError("simulated value error on update")
    monkeypatch.setattr("app.services.operational_settings.OperationalSettingsService.update_operational_settings", mock_update)
    payload = {
        "provider": "openai",
        "model_name": "gpt-4",
        "workspace_root": "/",
        "max_iterations_per_execution": 5,
        "daily_budget_usd": 10.0,
        "monthly_budget_usd": 100.0,
        "default_view": "chat",
        "activity_poll_seconds": 5,
        "heartbeat_interval_seconds": 60,
        "provider_keys": {"openai": "test-key"}
    }
    response = test_client.put("/settings/operational", json=payload)
    assert response.status_code == 400
    assert "simulated value error on update" in response.json()["detail"]

def test_update_operational_settings_secret_store_error(test_client: TestClient, monkeypatch) -> None:
    from app.core.secrets import SecretStoreError
    def mock_update(*args, **kwargs):
        raise SecretStoreError("simulated secret error on update")
    monkeypatch.setattr("app.services.operational_settings.OperationalSettingsService.update_operational_settings", mock_update)
    payload = {
        "provider": "openai",
        "model_name": "gpt-4",
        "workspace_root": "/",
        "max_iterations_per_execution": 5,
        "daily_budget_usd": 10.0,
        "monthly_budget_usd": 100.0,
        "default_view": "chat",
        "activity_poll_seconds": 5,
        "heartbeat_interval_seconds": 60,
        "provider_keys": {"openai": "test-key"}
    }
    response = test_client.put("/settings/operational", json=payload)
    assert response.status_code == 503
    assert "simulated secret error on update" in response.json()["detail"]
