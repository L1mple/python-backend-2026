import os
from uuid import uuid4

import pytest
from shop_api import database
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.fixture(scope="session", autouse=True)
def test_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Set TEST_DATABASE_URL to a PostgreSQL database before running tests"
        )
    engine = create_engine(url, pool_pre_ping=True)
    schema = "test_shop_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    test_engine = engine.execution_options(schema_translate_map={None: schema})
    patch = pytest.MonkeyPatch()
    patch.setattr(database, "engine", test_engine)
    try:
        database.initialize()
        yield test_engine
    finally:
        patch.undo()
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()
