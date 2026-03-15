import json
import sys
from pathlib import Path

from app.core.config import _read_env_list, _resolve_backend_root, clear_settings_cache

def test_read_env_list_empty(monkeypatch):
    monkeypatch.delenv("TEST_VAR", raising=False)
    assert _read_env_list("TEST_VAR") == ()
    assert _read_env_list("TEST_VAR", default=("a", "b")) == ("a", "b")

def test_read_env_list_json_array(monkeypatch):
    monkeypatch.setenv("TEST_VAR", '["a", "b", "c"]')
    assert _read_env_list("TEST_VAR") == ("a", "b", "c")

def test_read_env_list_json_invalid(monkeypatch):
    monkeypatch.setenv("TEST_VAR", '["a", "b", "c"') # Missing closing bracket
    assert _read_env_list("TEST_VAR", default=("def",)) == ("def",)

def test_read_env_list_json_not_array(monkeypatch):
    monkeypatch.setenv("TEST_VAR", '{"a": "b"}')
    # Starts with { not [ so it falls through to split
    assert _read_env_list("TEST_VAR") == ('{"a": "b"}',)

def test_read_env_list_json_not_list(monkeypatch):
    monkeypatch.setenv("TEST_VAR", '["a", 1, true]')
    assert _read_env_list("TEST_VAR") == ("a", "1", "True")

def test_read_env_list_json_empty_elements(monkeypatch):
    monkeypatch.setenv("TEST_VAR", '["a", "", " ", "b"]')
    assert _read_env_list("TEST_VAR") == ("a", "b")

def test_read_env_list_comma_separated(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "a,b,c")
    assert _read_env_list("TEST_VAR") == ("a", "b", "c")

def test_read_env_list_comma_separated_with_spaces(monkeypatch):
    monkeypatch.setenv("TEST_VAR", " a , b , c ")
    assert _read_env_list("TEST_VAR") == ("a", "b", "c")

def test_read_env_list_comma_separated_empty_elements(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "a,,b, ,c")
    assert _read_env_list("TEST_VAR") == ("a", "b", "c")

def test_resolve_backend_root_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass", raising=False)
    assert _resolve_backend_root() == Path("/tmp/meipass")

def test_clear_settings_cache():
    clear_settings_cache()

def test_read_env_list_json_not_list_type(monkeypatch):
    monkeypatch.setenv("TEST_VAR", '["a"]')
    monkeypatch.setattr(json, "loads", lambda *_args, **_kwargs: "not_a_list")
    assert _read_env_list("TEST_VAR", default=("x", "y")) == ("x", "y")
