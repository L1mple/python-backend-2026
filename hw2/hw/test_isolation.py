import pytest
from sqlalchemy import create_engine, text
import os

SQLALCHEMY_DATABASE_URL = "postgresql+psycopg2://shopuser:shoppass@localhost:5433/shopdb"

@pytest.fixture(scope="session")
def engine():
    eng = create_engine(SQLALCHEMY_DATABASE_URL, future=True)
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

def test_no_dirty_read_at_read_committed(conn_a, conn_b):
    trans_a = conn_a.begin()
    conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
    conn_a.execute(text("UPDATE accounts SET balance = 999 WHERE id = 1"))

    trans_b = conn_b.begin()
    conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
    result = conn_b.execute(
        text("SELECT balance FROM accounts WHERE id = 1")
    ).scalar()

    assert result == 500

    trans_b.rollback()
    trans_a.rollback()

def test_nonrepeatable_read_at_read_committed(conn_a, conn_b):
    trans_a = conn_a.begin()
    conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))

    first = conn_a.execute(
        text("SELECT balance FROM accounts WHERE id = 1")
    ).scalar()
    assert first == 500

    # B modifies and commits between A's two reads
    trans_b = conn_b.begin()
    conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
    conn_b.execute(text("UPDATE accounts SET balance = 999 WHERE id = 1"))
    trans_b.commit()

    second = conn_a.execute(
        text("SELECT balance FROM accounts WHERE id = 1")
    ).scalar()

    # Non-repeatable read occurs
    assert first != second
    assert second == 999

    trans_a.rollback()

def test_no_nonrepeatable_read_at_repeatable_read(conn_a, conn_b):
    trans_a = conn_a.begin()
    conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))

    first = conn_a.execute(
        text("SELECT balance FROM accounts WHERE id = 1")
    ).scalar()
    assert first == 500

    trans_b = conn_b.begin()
    conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
    conn_b.execute(text("UPDATE accounts SET balance = 999 WHERE id = 1"))
    trans_b.commit()

    second = conn_a.execute(
        text("SELECT balance FROM accounts WHERE id = 1")
    ).scalar()

    # The snapshot remains unchanged; both reads return 500
    assert first == second == 500

    trans_a.rollback()

def test_no_phantom_read_at_serializable(conn_a, conn_b):
    trans_a = conn_a.begin()
    conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

    count_first = conn_a.execute(
        text("SELECT COUNT(*) FROM accounts WHERE balance > 200")
    ).scalar()
    assert count_first == 2

    trans_b = conn_b.begin()
    conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
    conn_b.execute(text(
        "INSERT INTO accounts (id, owner, balance) VALUES (3, 'Carol', 700)"
    ))
    trans_b.commit()

    count_second = conn_a.execute(
        text("SELECT COUNT(*) FROM accounts WHERE balance > 200")
    ).scalar()

    assert count_second == 2

    trans_a.rollback()