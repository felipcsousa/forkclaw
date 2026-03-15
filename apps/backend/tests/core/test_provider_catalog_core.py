import pytest

from app.core.provider_catalog import (
    ProviderMetadata,
    get_default_model,
    get_provider_env_vars,
    get_provider_metadata,
    get_provider_tool_format,
    normalize_provider_id,
)


def test_normalize_provider_id():
    # Valid providers
    assert normalize_provider_id("openai") == "openai"
    assert normalize_provider_id("ANTHROPIC") == "anthropic"
    assert normalize_provider_id("  gemini  ") == "gemini"

    # Aliases
    assert normalize_provider_id("kimi-for-coding") == "kimi-coding"

    # Invalid providers
    with pytest.raises(ValueError, match="Provider is required"):
        normalize_provider_id("")

    with pytest.raises(ValueError, match="Provider is required"):
        normalize_provider_id("   ")

    with pytest.raises(ValueError, match="Unsupported provider `invalid-provider`"):
        normalize_provider_id("invalid-provider")


def test_get_provider_metadata():
    metadata = get_provider_metadata("openai")
    assert isinstance(metadata, ProviderMetadata)
    assert metadata.provider_id == "openai"
    assert metadata.label == "OpenAI"
    assert metadata.default_model == "gpt-4o-mini"
    assert metadata.tool_format == "openai"
    assert metadata.env_vars == ("OPENAI_API_KEY",)

    # Through alias
    metadata_kimi = get_provider_metadata("kimi-for-coding")
    assert metadata_kimi.provider_id == "kimi-coding"
    assert metadata_kimi.tool_format == "anthropic"


def test_get_default_model():
    assert get_default_model("openai") == "gpt-4o-mini"
    assert get_default_model("anthropic") == "claude-3-5-sonnet-latest"
    assert get_default_model("kimi-for-coding") == "k2p5"

    with pytest.raises(ValueError):
        get_default_model("invalid")


def test_get_provider_env_vars():
    assert get_provider_env_vars("openai") == ("OPENAI_API_KEY",)
    assert get_provider_env_vars("product_echo") == ()
    assert get_provider_env_vars("kimi-for-coding") == ("KIMI_CODING_API_KEY", "KIMI_API_KEY")

    with pytest.raises(ValueError):
        get_provider_env_vars("invalid")


def test_get_provider_tool_format_openai():
    # Many providers default to 'openai' format
    assert get_provider_tool_format("openai") == "openai"
    assert get_provider_tool_format("anthropic") == "openai"
    assert get_provider_tool_format("deepseek") == "openai"


def test_get_provider_tool_format_anthropic():
    # Providers explicitly setting format to 'anthropic'
    assert get_provider_tool_format("kimi-coding") == "anthropic"


def test_get_provider_tool_format_alias():
    # Should resolve aliases before checking format
    assert get_provider_tool_format("kimi-for-coding") == "anthropic"


def test_get_provider_tool_format_unsupported():
    with pytest.raises(ValueError, match="Unsupported provider `unsupported`"):
        get_provider_tool_format("unsupported")


def test_get_provider_tool_format_empty():
    with pytest.raises(ValueError, match="Provider is required"):
        get_provider_tool_format("")
    with pytest.raises(ValueError, match="Provider is required"):
        get_provider_tool_format(None)  # type: ignore
