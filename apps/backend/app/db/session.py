from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from sqlite3 import Connection as SQLite3Connection

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.core.config import get_settings


def _enable_sqlite_foreign_keys(dbapi_connection: SQLite3Connection, _: object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    settings.ensure_data_dir()
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def get_db_session() -> Session:
    return Session(get_engine())


def get_session() -> Generator[Session, None, None]:
    with get_db_session() as session:
        yield session


def clear_engine_cache() -> None:
    get_engine.cache_clear()
