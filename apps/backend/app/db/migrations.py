from __future__ import annotations

from alembic.config import Config

from alembic import command
from app.core.config import get_settings


def get_alembic_config() -> Config:
    settings = get_settings()
    config = Config(str(settings.backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(settings.backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def upgrade_database() -> None:
    settings = get_settings()
    settings.ensure_data_dir()
    command.upgrade(get_alembic_config(), "head")


if __name__ == "__main__":
    upgrade_database()
