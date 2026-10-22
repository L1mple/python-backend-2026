"""Use a unique PostgreSQL schema for each test run; never clear application data."""
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shop_api import database


@pytest.fixture(scope="session", autouse=True)
def test_database():
    schema = f"test_{uuid4().hex}"
    admin = database.engine
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(database.DATABASE_URL, connect_args={
        "options": f"-csearch_path={schema} -clock_timeout=5000 -cstatement_timeout=15000",
    })
    original = database.SessionLocal
    database.engine = engine
    database.SessionLocal = sessionmaker(engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        database.engine = admin
        database.SessionLocal = original
        engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
