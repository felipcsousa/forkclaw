from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from app.core.config import clear_settings_cache, get_settings
from app.core.secrets import clear_secret_store_cache
from app.db.seed import seed_default_data
from app.db.session import clear_engine_cache, get_db_session
from app.main import create_app


def _alembic_config() -> Config:
    settings = get_settings()
    config = Config(str(settings.backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(settings.backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


@pytest.fixture
def test_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "agent_os_test.db"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "notes.txt").write_text("hello workspace", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_WORKSPACE_ROOT", str(workspace_root))
    monkeypatch.setenv("SCHEDULER_POLL_INTERVAL_SECONDS", "0.2")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "0.4")
    monkeypatch.setenv("STALE_TASK_RUN_SECONDS", "1")
    monkeypatch.setenv("APP_SECRET_BACKEND", "memory")

    clear_settings_cache()
    clear_secret_store_cache()
    clear_engine_cache()

    command.upgrade(_alembic_config(), "head")
    with get_db_session() as session:
        seed_default_data(session)

    with TestClient(create_app()) as client:
        yield client

    clear_engine_cache()
    clear_settings_cache()
    clear_secret_store_cache()
