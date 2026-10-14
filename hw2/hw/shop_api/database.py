import os
from collections.abc import Iterator
from functools import lru_cache
from sqlite3 import Connection
from typing import Annotated, Any

from fastapi import Depends
from shop_api.models import Base
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool


def create_db_engine(url: str) -> Engine:
    """Настроить PostgreSQL или SQLite, включая внешние ключи SQLite."""
    if url.startswith("sqlite:"):
        options: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            options["poolclass"] = StaticPool
        engine = create_engine(url, **options)

        @event.listens_for(engine, "connect")
        def configure_sqlite(
            connection: Connection, _record: ConnectionPoolEntry
        ) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    """Создать схему один раз; без DATABASE_URL использовать файл SQLite."""
    engine = create_db_engine(os.getenv("DATABASE_URL", "sqlite:///./shop.db"))
    Base.metadata.create_all(engine)
    return engine


def get_session() -> Iterator[Session]:
    """Выполнить запрос API в одной транзакции, откатывая ошибки."""
    with Session(get_engine(), expire_on_commit=False) as session, session.begin():
        yield session


DbSession = Annotated[Session, Depends(get_session, scope="function")]
