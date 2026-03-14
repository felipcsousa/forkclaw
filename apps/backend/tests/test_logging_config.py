from __future__ import annotations

import json
import logging

from app.core.config import clear_settings_cache
from app.core.logging import configure_logging


def _reset_logging_state() -> None:
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    if hasattr(root_logger, "_nanobot_configured"):
        delattr(root_logger, "_nanobot_configured")


def _flush_handlers() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_configure_logging_writes_structured_json(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("APP_LOG_DIR", str(log_dir))
    clear_settings_cache()
    _reset_logging_state()

    log_path = configure_logging()
    logger = logging.getLogger("nanobot.test")
    logger.info("structured log test", extra={"request_id": "req-1", "attempt": 2})
    _flush_handlers()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[-1])
    assert payload["level"] == "INFO"
    assert payload["logger"] == "nanobot.test"
    assert payload["message"] == "structured log test"
    assert payload["extra"]["request_id"] == "req-1"
    assert payload["extra"]["attempt"] == 2

    _reset_logging_state()
    clear_settings_cache()


def test_configure_logging_rotates_file(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("APP_LOG_DIR", str(log_dir))
    monkeypatch.setenv("APP_LOG_MAX_BYTES", "256")
    monkeypatch.setenv("APP_LOG_BACKUP_COUNT", "2")
    clear_settings_cache()
    _reset_logging_state()

    log_path = configure_logging()
    logger = logging.getLogger("nanobot.rotation")
    for index in range(120):
        logger.info("rotation-%s-%s", index, "x" * 40)
    _flush_handlers()

    rotated_paths = sorted(log_path.parent.glob("backend.log.*"))
    assert rotated_paths
    assert any(path.name == "backend.log.1" for path in rotated_paths)

    _reset_logging_state()
    clear_settings_cache()
