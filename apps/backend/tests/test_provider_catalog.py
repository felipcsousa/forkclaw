import pytest

from app.core.provider_catalog import get_provider_env_vars

def test_get_provider_env_vars_standard():
    assert get_provider_env_vars("openai") == ("OPENAI_API_KEY",)
    assert get_provider_env_vars("anthropic") == ("ANTHROPIC_API_KEY",)

def test_get_provider_env_vars_alias():
    # kimi-for-coding is an alias for kimi-coding
    assert get_provider_env_vars("kimi-for-coding") == ("KIMI_CODING_API_KEY", "KIMI_API_KEY")

def test_get_provider_env_vars_empty_vars():
    assert get_provider_env_vars("product_echo") == ()

def test_get_provider_env_vars_unsupported():
    with pytest.raises(ValueError, match="Unsupported provider `unsupported_provider`"):
        get_provider_env_vars("unsupported_provider")

def test_get_provider_env_vars_empty_or_none():
    with pytest.raises(ValueError, match="Provider is required"):
        get_provider_env_vars("")

    with pytest.raises(ValueError, match="Provider is required"):
        get_provider_env_vars(None)  # type: ignore

def test_get_provider_env_vars_case_insensitive_and_whitespace():
    assert get_provider_env_vars("  OPENAI  ") == ("OPENAI_API_KEY",)
    assert get_provider_env_vars("\nAnthropic\t") == ("ANTHROPIC_API_KEY",)
