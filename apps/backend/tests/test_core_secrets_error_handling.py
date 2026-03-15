import pytest
import keyring
from keyring.errors import KeyringError, NoKeyringError

from app.core.secrets import KeychainSecretStore, SecretStoreError


@pytest.fixture
def store():
    return KeychainSecretStore("test_service")


@pytest.mark.parametrize("error_class", [KeyringError, NoKeyringError])
def test_get_provider_api_key_errors(store, monkeypatch, error_class):
    def mock_get_password(*args, **kwargs):
        raise error_class("Mocked error")

    monkeypatch.setattr(keyring, "get_password", mock_get_password)

    with pytest.raises(SecretStoreError, match="System keychain is unavailable. Configure a supported credential store."):
        store.get_provider_api_key("openai")


@pytest.mark.parametrize("error_class", [KeyringError, NoKeyringError])
def test_set_provider_api_key_errors(store, monkeypatch, error_class):
    def mock_set_password(*args, **kwargs):
        raise error_class("Mocked error")

    monkeypatch.setattr(keyring, "set_password", mock_set_password)

    with pytest.raises(SecretStoreError, match="System keychain is unavailable. Could not save the provider API key."):
        store.set_provider_api_key("openai", "sk-12345")


@pytest.mark.parametrize("error_class", [KeyringError, NoKeyringError])
def test_delete_provider_api_key_errors(store, monkeypatch, error_class):
    def mock_delete_password(*args, **kwargs):
        raise error_class("Mocked error")

    monkeypatch.setattr(keyring, "delete_password", mock_delete_password)

    with pytest.raises(SecretStoreError, match="System keychain is unavailable. Could not delete the provider API key."):
        store.delete_provider_api_key("openai")


def test_delete_provider_api_key_password_delete_error(store, monkeypatch):
    def mock_delete_password(*args, **kwargs):
        raise keyring.errors.PasswordDeleteError("Mocked error")

    monkeypatch.setattr(keyring, "delete_password", mock_delete_password)

    # Should not raise an exception
    store.delete_provider_api_key("openai")


@pytest.mark.parametrize("error_class", [KeyringError, NoKeyringError])
def test_get_skill_env_value_errors(store, monkeypatch, error_class):
    def mock_get_password(*args, **kwargs):
        raise error_class("Mocked error")

    monkeypatch.setattr(keyring, "get_password", mock_get_password)

    with pytest.raises(SecretStoreError, match="System keychain is unavailable. Configure a supported credential store."):
        store.get_skill_env_value("test_skill", "API_KEY")


@pytest.mark.parametrize("error_class", [KeyringError, NoKeyringError])
def test_set_skill_env_value_errors(store, monkeypatch, error_class):
    def mock_set_password(*args, **kwargs):
        raise error_class("Mocked error")

    monkeypatch.setattr(keyring, "set_password", mock_set_password)

    with pytest.raises(SecretStoreError, match="System keychain is unavailable. Could not save the skill secret."):
        store.set_skill_env_value("test_skill", "API_KEY", "value")


@pytest.mark.parametrize("error_class", [KeyringError, NoKeyringError])
def test_delete_skill_env_value_errors(store, monkeypatch, error_class):
    def mock_delete_password(*args, **kwargs):
        raise error_class("Mocked error")

    monkeypatch.setattr(keyring, "delete_password", mock_delete_password)

    with pytest.raises(SecretStoreError, match="System keychain is unavailable. Could not delete the skill secret."):
        store.delete_skill_env_value("test_skill", "API_KEY")


def test_delete_skill_env_value_password_delete_error(store, monkeypatch):
    def mock_delete_password(*args, **kwargs):
        raise keyring.errors.PasswordDeleteError("Mocked error")

    monkeypatch.setattr(keyring, "delete_password", mock_delete_password)

    # Should not raise an exception
    store.delete_skill_env_value("test_skill", "API_KEY")
