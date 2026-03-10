from __future__ import annotations

from functools import lru_cache
from typing import Protocol

import keyring
from keyring.errors import KeyringError, NoKeyringError

from app.core.config import get_settings
from app.core.provider_catalog import normalize_provider_id


class SecretStoreError(RuntimeError):
    """Raised when the configured secret backend is unavailable."""


class SecretStore(Protocol):
    def get_provider_api_key(self, provider: str) -> str | None:
        """Load the provider API key from the configured secure backend."""

    def set_provider_api_key(self, provider: str, value: str) -> None:
        """Persist the provider API key in the configured secure backend."""

    def delete_provider_api_key(self, provider: str) -> None:
        """Delete the provider API key from the configured secure backend."""

    def get_skill_env_value(self, skill_key: str, env_name: str) -> str | None:
        """Load a skill-scoped environment value from the configured secure backend."""

    def set_skill_env_value(self, skill_key: str, env_name: str, value: str) -> None:
        """Persist a skill-scoped environment value in the configured secure backend."""

    def delete_skill_env_value(self, skill_key: str, env_name: str) -> None:
        """Delete a skill-scoped environment value from the configured secure backend."""


class KeychainSecretStore:
    def __init__(self, service_name: str):
        self.service_name = service_name

    def get_provider_api_key(self, provider: str) -> str | None:
        provider = normalize_provider_id(provider)
        try:
            return keyring.get_password(self.service_name, self._account_name(provider))
        except (KeyringError, NoKeyringError) as exc:
            raise SecretStoreError(
                "System keychain is unavailable. Configure a supported credential store."
            ) from exc

    def set_provider_api_key(self, provider: str, value: str) -> None:
        provider = normalize_provider_id(provider)
        try:
            keyring.set_password(self.service_name, self._account_name(provider), value)
        except (KeyringError, NoKeyringError) as exc:
            raise SecretStoreError(
                "System keychain is unavailable. Could not save the provider API key."
            ) from exc

    def delete_provider_api_key(self, provider: str) -> None:
        provider = normalize_provider_id(provider)
        try:
            keyring.delete_password(self.service_name, self._account_name(provider))
        except keyring.errors.PasswordDeleteError:
            return
        except (KeyringError, NoKeyringError) as exc:
            raise SecretStoreError(
                "System keychain is unavailable. Could not delete the provider API key."
            ) from exc

    def get_skill_env_value(self, skill_key: str, env_name: str) -> str | None:
        try:
            account = self._skill_env_account(skill_key, env_name)
            return keyring.get_password(self.service_name, account)
        except (KeyringError, NoKeyringError) as exc:
            raise SecretStoreError(
                "System keychain is unavailable. Configure a supported credential store."
            ) from exc

    def set_skill_env_value(self, skill_key: str, env_name: str, value: str) -> None:
        try:
            keyring.set_password(
                self.service_name,
                self._skill_env_account(skill_key, env_name),
                value,
            )
        except (KeyringError, NoKeyringError) as exc:
            raise SecretStoreError(
                "System keychain is unavailable. Could not save the skill secret."
            ) from exc

    def delete_skill_env_value(self, skill_key: str, env_name: str) -> None:
        try:
            keyring.delete_password(
                self.service_name,
                self._skill_env_account(skill_key, env_name),
            )
        except keyring.errors.PasswordDeleteError:
            return
        except (KeyringError, NoKeyringError) as exc:
            raise SecretStoreError(
                "System keychain is unavailable. Could not delete the skill secret."
            ) from exc

    @staticmethod
    def _account_name(provider: str) -> str:
        return f"provider:{provider}:api_key"

    @staticmethod
    def _skill_env_account(skill_key: str, env_name: str) -> str:
        return f"skill:{skill_key}:env:{env_name}"


class MemorySecretStore:
    def __init__(self):
        self._values: dict[str, str] = {}
        self._skill_env_values: dict[tuple[str, str], str] = {}

    def get_provider_api_key(self, provider: str) -> str | None:
        provider = normalize_provider_id(provider)
        return self._values.get(provider)

    def set_provider_api_key(self, provider: str, value: str) -> None:
        provider = normalize_provider_id(provider)
        self._values[provider] = value

    def delete_provider_api_key(self, provider: str) -> None:
        provider = normalize_provider_id(provider)
        self._values.pop(provider, None)

    def get_skill_env_value(self, skill_key: str, env_name: str) -> str | None:
        return self._skill_env_values.get((skill_key, env_name))

    def set_skill_env_value(self, skill_key: str, env_name: str, value: str) -> None:
        self._skill_env_values[(skill_key, env_name)] = value

    def delete_skill_env_value(self, skill_key: str, env_name: str) -> None:
        self._skill_env_values.pop((skill_key, env_name), None)


@lru_cache
def get_secret_store() -> SecretStore:
    settings = get_settings()
    if settings.secret_backend == "memory":
        return MemorySecretStore()
    return KeychainSecretStore(settings.secret_service_name)


def clear_secret_store_cache() -> None:
    get_secret_store.cache_clear()
