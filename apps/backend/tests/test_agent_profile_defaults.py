import pytest
from app.core.agent_profile_defaults import summarize_persona

def test_summarize_persona_empty():
    assert summarize_persona("") == "local-first operator"

def test_summarize_persona_whitespace():
    assert summarize_persona("   ") == "local-first operator"

def test_summarize_persona_short_no_period():
    text = "This is a short soul text"
    assert summarize_persona(text) == text

def test_summarize_persona_with_period():
    text = "This is the first sentence. This is the second sentence."
    assert summarize_persona(text) == "This is the first sentence"

def test_summarize_persona_long_text():
    text = "A" * 300
    assert summarize_persona(text) == "A" * 200

def test_summarize_persona_long_text_with_period():
    text = "A" * 250 + ". This is the second sentence."
    assert summarize_persona(text) == "A" * 200

def test_summarize_persona_period_at_start():
    text = ". Hello"
    assert summarize_persona(text) == "local-first operator"
