from __future__ import annotations

from functools import lru_cache
from typing import Protocol

import keyring
from keyring.errors import KeyringError, NoKeyringError

from app.core.config import get_settings


class SecretStoreError(RuntimeError):
    """Raised when the configured secret backend is unavailable."""


class SecretStore(Protocol):
    def get_provider_api_key(self, provider: str) -> str | None:
        """Load the provider API key from the configured secure backend."""

    def set_provider_api_key(self, provider: str, value: str) -> None:
        """Persist the provider API key in the configured secure backend."""

    def delete_provider_api_key(self, provider: str) -> None:
        """Delete the provider API key from the configured secure backend."""


class KeychainSecretStore:
    def __init__(self, service_name: str):
        self.service_name = service_name

    def get_provider_api_key(self, provider: str) -> str | None:
        try:
            return keyring.get_password(self.service_name, self._account_name(provider))
        except (KeyringError, NoKeyringError) as exc:
            raise SecretStoreError(
                "System keychain is unavailable. Configure a supported credential store."
            ) from exc

    def set_provider_api_key(self, provider: str, value: str) -> None:
        try:
            keyring.set_password(self.service_name, self._account_name(provider), value)
        except (KeyringError, NoKeyringError) as exc:
            raise SecretStoreError(
                "System keychain is unavailable. Could not save the provider API key."
            ) from exc

    def delete_provider_api_key(self, provider: str) -> None:
        try:
            keyring.delete_password(self.service_name, self._account_name(provider))
        except keyring.errors.PasswordDeleteError:
            return
        except (KeyringError, NoKeyringError) as exc:
            raise SecretStoreError(
                "System keychain is unavailable. Could not delete the provider API key."
            ) from exc

    @staticmethod
    def _account_name(provider: str) -> str:
        return f"provider:{provider}:api_key"


class MemorySecretStore:
    def __init__(self):
        self._values: dict[str, str] = {}

    def get_provider_api_key(self, provider: str) -> str | None:
        return self._values.get(provider)

    def set_provider_api_key(self, provider: str, value: str) -> None:
        self._values[provider] = value

    def delete_provider_api_key(self, provider: str) -> None:
        self._values.pop(provider, None)


@lru_cache
def get_secret_store() -> SecretStore:
    settings = get_settings()
    if settings.secret_backend == "memory":
        return MemorySecretStore()
    return KeychainSecretStore(settings.secret_service_name)


def clear_secret_store_cache() -> None:
    get_secret_store.cache_clear()
