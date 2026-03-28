from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.secrets import SecretStoreError
from app.schemas.operational_settings import (
    OperationalSettingsRead,
    OperationalSettingsUpdate,
)


# Mock OperationalSettingsService responses
def test_get_operational_settings_success(test_client: TestClient, monkeypatch) -> None:
    from app.services.operational_settings import OperationalSettingsService

    def mock_get(*args, **kwargs):
        return OperationalSettingsRead(
            provider="openai",
            model_name="gpt-4",
            workspace_root="/tmp",
            max_iterations_per_execution=5,
            daily_budget_usd=10.0,
            monthly_budget_usd=100.0,
            default_view="chat",
            activity_poll_seconds=10,
            heartbeat_interval_seconds=60,
            provider_api_key_configured=True,
        )

    monkeypatch.setattr(OperationalSettingsService, "get_operational_settings", mock_get)

    response = test_client.get("/settings/operational")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"


def test_get_operational_settings_value_error(test_client: TestClient, monkeypatch) -> None:
    from app.services.operational_settings import OperationalSettingsService

    def mock_get(*args, **kwargs):
        raise ValueError("Profile not found")

    monkeypatch.setattr(OperationalSettingsService, "get_operational_settings", mock_get)

    response = test_client.get("/settings/operational")
    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


def test_get_operational_settings_secret_error(test_client: TestClient, monkeypatch) -> None:
    from app.services.operational_settings import OperationalSettingsService

    def mock_get(*args, **kwargs):
        raise SecretStoreError("Store unavailable")

    monkeypatch.setattr(OperationalSettingsService, "get_operational_settings", mock_get)

    response = test_client.get("/settings/operational")
    assert response.status_code == 503
    assert response.json()["detail"] == "Store unavailable"


def test_update_operational_settings_success(test_client: TestClient, monkeypatch) -> None:
    from app.services.operational_settings import OperationalSettingsService

    def mock_update(self, payload: OperationalSettingsUpdate):
        return OperationalSettingsRead(
            provider=payload.provider,
            model_name=payload.model_name,
            workspace_root=payload.workspace_root,
            max_iterations_per_execution=payload.max_iterations_per_execution,
            daily_budget_usd=payload.daily_budget_usd,
            monthly_budget_usd=payload.monthly_budget_usd,
            default_view=payload.default_view,
            activity_poll_seconds=payload.activity_poll_seconds,
            heartbeat_interval_seconds=payload.heartbeat_interval_seconds,
            provider_api_key_configured=True,
        )

    monkeypatch.setattr(OperationalSettingsService, "update_operational_settings", mock_update)

    payload = {
        "provider": "anthropic",
        "model_name": "claude",
        "workspace_root": "/tmp/new",
        "max_iterations_per_execution": 5,
        "daily_budget_usd": 5.0,
        "monthly_budget_usd": 50.0,
        "default_view": "chat",
        "activity_poll_seconds": 10,
        "heartbeat_interval_seconds": 60,
        "api_key": "secret",
    }

    response = test_client.put("/settings/operational", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "anthropic"


def test_update_operational_settings_value_error(test_client: TestClient, monkeypatch) -> None:
    from app.services.operational_settings import OperationalSettingsService

    def mock_update(self, payload: OperationalSettingsUpdate):
        raise ValueError("Invalid budget")

    monkeypatch.setattr(OperationalSettingsService, "update_operational_settings", mock_update)

    payload = {
        "provider": "anthropic",
        "model_name": "claude",
        "workspace_root": "/tmp/new",
        "max_iterations_per_execution": 5,
        "daily_budget_usd": 50.0,
        "monthly_budget_usd": 50.0,
        "default_view": "chat",
        "activity_poll_seconds": 10,
        "heartbeat_interval_seconds": 60,
        "api_key": "secret",
    }

    response = test_client.put("/settings/operational", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid budget"


def test_update_operational_settings_secret_error(test_client: TestClient, monkeypatch) -> None:
    from app.services.operational_settings import OperationalSettingsService

    def mock_update(self, payload: OperationalSettingsUpdate):
        raise SecretStoreError("Store read-only")

    monkeypatch.setattr(OperationalSettingsService, "update_operational_settings", mock_update)

    payload = {
        "provider": "anthropic",
        "model_name": "claude",
        "workspace_root": "/tmp/new",
        "max_iterations_per_execution": 5,
        "daily_budget_usd": 5.0,
        "monthly_budget_usd": 50.0,
        "default_view": "chat",
        "activity_poll_seconds": 10,
        "heartbeat_interval_seconds": 60,
        "api_key": "secret",
    }

    response = test_client.put("/settings/operational", json=payload)
    assert response.status_code == 503
    assert response.json()["detail"] == "Store read-only"
