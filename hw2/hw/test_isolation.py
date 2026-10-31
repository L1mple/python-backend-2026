import pytest
from sqlalchemy import create_engine, text

PG_DSN = "postgresql+psycopg2://postgres:postgres@localhost:5432/test_iso"

@pytest.fixture(scope="session")
def engine():
    eng = create_engine(PG_DSN, future=True)
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS accounts"))
        conn.execute(text("""
            CREATE TABLE accounts (
                id      INTEGER PRIMARY KEY,
                owner   TEXT NOT NULL,
                balance INTEGER NOT NULL
            )
        """))
    yield eng
    eng.dispose()

@pytest.fixture(autouse=True)
def reset_data(engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE accounts"))
        conn.execute(text("""
            INSERT INTO accounts (id, owner, balance) VALUES
                (1, 'Alice', 500),
                (2, 'Bob',   300)
        """))
    yield

@pytest.fixture
def conn_a(engine):
    with engine.connect() as conn:
        yield conn

@pytest.fixture
def conn_b(engine):
    with engine.connect() as conn:
        yield conn