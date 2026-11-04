"""Подключение к БД (SQLAlchemy) и создание таблиц."""

import os
import time
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://shop:shop@localhost:5432/shop")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db(attempts: int = 30, delay: float = 1.0) -> None:
    """Создает таблицы. Если БД еще стартует (например, в docker compose), ждет ее."""
    from shop_api import models  # noqa: F401  (регистрирует таблицы в Base.metadata)

    for attempt in range(1, attempts + 1):
        try:
            Base.metadata.create_all(engine)
            return
        except OperationalError:
            if attempt == attempts:
                raise
            time.sleep(delay)


def get_session() -> Iterator[Session]:
    """FastAPI-зависимость: одна сессия на запрос."""
    with SessionLocal() as session:
        yield session
