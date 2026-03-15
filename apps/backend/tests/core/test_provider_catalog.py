from __future__ import annotations

import pytest

from app.core.provider_catalog import (
    get_default_model,
    get_provider_metadata,
    get_provider_tool_format,
    normalize_provider_id,
)


@pytest.mark.parametrize(
    ("raw_provider", "canonical_provider"),
    [
        ("openai", "openai"),
        (" OPENAI ", "openai"),
        ("kimi-for-coding", "kimi-coding"),
        (" KIMI-FOR-CODING ", "kimi-coding"),
    ],
)
def test_normalize_provider_id_handles_case_whitespace_and_aliases(
    raw_provider: str, canonical_provider: str
) -> None:
    assert normalize_provider_id(raw_provider) == canonical_provider


def test_normalize_provider_id_rejects_blank_provider() -> None:
    with pytest.raises(ValueError, match="Provider is required"):
        normalize_provider_id("   ")


def test_normalize_provider_id_rejects_unsupported_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported provider `bogus`"):
        normalize_provider_id("bogus")


def test_get_provider_metadata_returns_expected_values() -> None:
    metadata = get_provider_metadata("kimi-for-coding")

    assert metadata.provider_id == "kimi-coding"
    assert metadata.label == "Kimi for Coding"
    assert metadata.default_model == "k2p5"
    assert metadata.tool_format == "anthropic"


@pytest.mark.parametrize(
    ("provider", "expected_model"),
    [
        ("openai", "gpt-4o-mini"),
        (" kimi-for-coding ", "k2p5"),
    ],
)
def test_get_default_model_returns_catalog_defaults(provider: str, expected_model: str) -> None:
    assert get_default_model(provider) == expected_model


@pytest.mark.parametrize(
    ("provider", "expected_format"),
    [
        ("openai", "openai"),
        ("kimi-for-coding", "anthropic"),
    ],
)
def test_get_provider_tool_format_returns_expected_mapping(
    provider: str, expected_format: str
) -> None:
    assert get_provider_tool_format(provider) == expected_format
