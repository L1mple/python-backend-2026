"""Run unchanged instructor tests against isolated SQL databases."""

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from shop_api import database
from sqlalchemy import Engine, create_engine
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.fixture(scope="session")
def database_factory() -> Callable[[Path], AbstractContextManager[Engine]]:
    @contextmanager
    def create_test_database(path: Path) -> Iterator[Engine]:
        url = os.getenv("HW4_TEST_DATABASE_URL")
        schema = f"hw4_test_{uuid4().hex}"
        engine = create_engine(url or f"sqlite:///{path / 'shop.sqlite3'}")
        if url:
            with engine.begin() as connection:
                connection.execute(CreateSchema(schema))
            engine = engine.execution_options(schema_translate_map={None: schema})
        database.Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            if url:
                with engine.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
            engine.dispose()

    return create_test_database


@pytest.fixture(scope="session", autouse=True)
def instructor_database(
    database_factory: Callable[[Path], AbstractContextManager[Engine]],
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    original = database.engine
    with database_factory(tmp_path_factory.mktemp("instructor")) as engine:
        database.engine = engine
        try:
            yield
        finally:
            database.engine = original
