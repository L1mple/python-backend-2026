from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://ADMIN:123@127.0.0.1:5432/DB",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_session():
    with SessionLocal() as session:
        yield session


def create_tables() -> None:
    from . import tables  # noqa: F401  — регистрация моделей в Base.metadata

    Base.metadata.create_all(engine)
