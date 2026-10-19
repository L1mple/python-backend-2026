import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from shop_api import database, main
from shop_api.models import Base
from sqlalchemy import Engine, text


@pytest.fixture()
def db_engine(tmp_path: Path) -> Iterator[Engine]:
    """Изолировать тест в схеме PostgreSQL или во временном файле SQLite."""
    url = os.getenv("DATABASE_URL", "")
    if url.startswith("postgresql"):
        engine = database.create_db_engine(url)
        schema = f"hw5_test_{uuid4().hex}"
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
        scoped = engine.execution_options(schema_translate_map={None: schema})
        try:
            Base.metadata.create_all(scoped)
            yield scoped
        finally:
            with engine.begin() as connection:
                connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
            engine.dispose()
    else:
        engine = database.create_db_engine(f"sqlite:///{tmp_path / 'shop.db'}")
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture()
def client(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Запускать настоящий API и его транзакции на изолированной тестовой БД."""
    monkeypatch.setattr(database, "get_engine", lambda: db_engine)
    monkeypatch.setattr(main, "get_engine", lambda: db_engine)
    with TestClient(main.app) as test_client:
        yield test_client
