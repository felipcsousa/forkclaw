from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ToolFormat = Literal["openai", "anthropic"]


@dataclass(frozen=True)
class ProviderMetadata:
    provider_id: str
    label: str
    default_model: str
    tool_format: ToolFormat = "openai"
    api_base: str | None = None
    protocol: str | None = None
    env_vars: tuple[str, ...] = ()


PROVIDER_ALIASES = {
    "kimi-for-coding": "kimi-coding",
}

PROVIDERS = {
    "product_echo": ProviderMetadata(
        provider_id="product_echo",
        label="Product Echo",
        default_model="product-echo/simple",
    ),
    "openai": ProviderMetadata(
        provider_id="openai",
        label="OpenAI",
        default_model="gpt-4o-mini",
        env_vars=("OPENAI_API_KEY",),
    ),
    "anthropic": ProviderMetadata(
        provider_id="anthropic",
        label="Anthropic",
        default_model="claude-3-5-sonnet-latest",
        env_vars=("ANTHROPIC_API_KEY",),
    ),
    "openrouter": ProviderMetadata(
        provider_id="openrouter",
        label="OpenRouter",
        default_model="openai/gpt-4o-mini",
        env_vars=("OPENROUTER_API_KEY",),
    ),
    "deepseek": ProviderMetadata(
        provider_id="deepseek",
        label="DeepSeek",
        default_model="deepseek-chat",
        env_vars=("DEEPSEEK_API_KEY",),
    ),
    "gemini": ProviderMetadata(
        provider_id="gemini",
        label="Gemini",
        default_model="gemini-2.0-flash",
        env_vars=("GEMINI_API_KEY",),
    ),
    "kimi-coding": ProviderMetadata(
        provider_id="kimi-coding",
        label="Kimi for Coding",
        default_model="k2p5",
        tool_format="anthropic",
        api_base="https://api.kimi.com/coding/",
        protocol="anthropic-messages",
        env_vars=("KIMI_CODING_API_KEY", "KIMI_API_KEY"),
    ),
}

SUPPORTED_PROVIDER_IDS = tuple(PROVIDERS)
SUPPORTED_PROVIDER_TEXT = ", ".join(f"`{provider}`" for provider in SUPPORTED_PROVIDER_IDS)


def normalize_provider_id(provider: str) -> str:
    candidate = (provider or "").strip().lower()
    if not candidate:
        raise ValueError(f"Provider is required. Supported providers: {SUPPORTED_PROVIDER_TEXT}.")

    canonical = PROVIDER_ALIASES.get(candidate, candidate)
    if canonical not in PROVIDERS:
        raise ValueError(
            f"Unsupported provider `{provider}`. Supported providers: {SUPPORTED_PROVIDER_TEXT}."
        )
    return canonical


def get_provider_metadata(provider: str) -> ProviderMetadata:
    return PROVIDERS[normalize_provider_id(provider)]


def get_default_model(provider: str) -> str:
    return get_provider_metadata(provider).default_model


def get_provider_env_vars(provider: str) -> tuple[str, ...]:
    return get_provider_metadata(provider).env_vars


def get_provider_tool_format(provider: str) -> ToolFormat:
    return get_provider_metadata(provider).tool_format
