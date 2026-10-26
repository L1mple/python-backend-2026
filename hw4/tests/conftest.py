import pytest
from sqlalchemy import text

from store.db import Base, engine, init_db


@pytest.fixture(scope="session", autouse=True)
def clean_database() -> None:
    # module-level TestClient(app) doesn't run lifespan
    init_db()
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY"))
