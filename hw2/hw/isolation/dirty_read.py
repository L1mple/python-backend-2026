"""
Dirty read: читаем данные, которые другая транзакция ещё не закоммитила. Разрешён на READ UNCOMMITTED, запрещён на READ COMMITTED+.

Postgres настоящий READ UNCOMMITTED не поддерживает и повышает его до READ COMMITTED, поэтому dirty read здесь не воспроизводится ни на одном уровне.
"""

import os

from sqlalchemy import create_engine, text

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:password@localhost:7432/shop_db",
)
engine = create_engine(DB_URL, future=True)


def setup():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS isolation_test"))
        conn.execute(text("CREATE TABLE isolation_test (id int primary key, value int)"))
        conn.execute(text("INSERT INTO isolation_test (id, value) VALUES (1, 1)"))


def demo(level: str) -> None:
    setup()
    print(f"\n--- Level: {level} ---")

    # Session 1: пишет, но НЕ коммитит.
    conn1 = engine.connect().execution_options(isolation_level=level)
    tx1 = conn1.begin()
    conn1.execute(text("UPDATE isolation_test SET value = 100 WHERE id = 1"))
    print("Session 1 wrote value=100, but not committed yet")

    # Session 2: читает ту же строку.
    conn2 = engine.connect().execution_options(isolation_level=level)
    tx2 = conn2.begin()
    seen = conn2.execute(text("SELECT value FROM isolation_test WHERE id = 1")).scalar()
    print(f"Session 2 sees value = {seen}")
    print("=> dirty read" if seen == 100 else "=> no dirty read (correct)")

    tx1.rollback()
    tx2.rollback()
    conn1.close()
    conn2.close()


if __name__ == "__main__":
    demo("READ UNCOMMITTED")
    demo("READ COMMITTED")
