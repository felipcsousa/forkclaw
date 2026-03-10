from __future__ import annotations

from dataclasses import dataclass

from nanobot.providers import LiteLLMProvider
from nanobot.providers.base import LLMProvider

from app.adapters.kernel.kimi_coding import KimiCodingProvider
from app.core.provider_catalog import (
    get_provider_env_vars,
    get_provider_metadata,
    get_provider_tool_format,
    normalize_provider_id,
)
from app.core.secrets import get_secret_store
from app.skills.runtime import runtime_env


@dataclass(frozen=True)
class ResolvedProvider:
    provider_name: str
    provider: LLMProvider
    tool_format: str


def resolve_provider_name(provider_name: str | None) -> str:
    return normalize_provider_id((provider_name or "product_echo").strip() or "product_echo")


def resolve_provider_api_key(provider_name: str) -> str | None:
    canonical_name = resolve_provider_name(provider_name)

    if canonical_name != "product_echo":
        secret_value = get_secret_store().get_provider_api_key(canonical_name)
        if secret_value:
            return secret_value

    candidate_names = (
        get_provider_env_vars(canonical_name)
        if canonical_name == "kimi-coding"
        else ("NANOBOT_API_KEY", *get_provider_env_vars(canonical_name))
    )
    for name in candidate_names:
        value = runtime_env(name)
        if value:
            return value

    return None


def missing_api_key_message(provider_name: str) -> str:
    canonical_name = resolve_provider_name(provider_name)
    if canonical_name == "kimi-coding":
        env_var_text = ", ".join(get_provider_env_vars(canonical_name))
        return (
            "Provider `kimi-coding` is configured but no API key was found. "
            f"Store it in the system keychain or set one of: {env_var_text}."
        )
    return (
        f"Provider `{canonical_name}` is configured but no API key is stored "
        "in the system keychain."
    )


def build_provider(
    *,
    provider_name: str | None,
    model_name: str,
    product_echo_factory,
) -> ResolvedProvider:
    canonical_name = resolve_provider_name(provider_name)

    if canonical_name == "product_echo":
        return ResolvedProvider(
            provider_name=canonical_name,
            provider=product_echo_factory(),
            tool_format=get_provider_tool_format(canonical_name),
        )

    api_key = resolve_provider_api_key(canonical_name)
    if not api_key:
        raise ValueError(missing_api_key_message(canonical_name))

    if canonical_name == "kimi-coding":
        metadata = get_provider_metadata(canonical_name)
        provider: LLMProvider = KimiCodingProvider(
            api_key=api_key,
            api_base=metadata.api_base,
            default_model=model_name,
        )
    else:
            provider = LiteLLMProvider(
            api_key=api_key,
            api_base=runtime_env("NANOBOT_API_BASE"),
            default_model=model_name,
            provider_name=canonical_name,
        )

    return ResolvedProvider(
        provider_name=canonical_name,
        provider=provider,
        tool_format=get_provider_tool_format(canonical_name),
    )
