"""
Non-repeatable read - транзакция дважды читает одну и ту же строку и получает РАЗНЫЕ значения, потому что между чтениями другая транзакция изменила и закоммитила эту строку.

Ожидание:
READ COMMITTED  -> non-repeatable = YES
REPEATABLE READ -> non-repeatable = NO
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

    conn1 = engine.connect().execution_options(isolation_level=level)
    tx1 = conn1.begin()
    v1 = conn1.execute(text("SELECT value FROM isolation_test WHERE id = 1")).scalar()
    print(f"Session 1 first read:  {v1}")

    conn2 = engine.connect().execution_options(isolation_level=level)
    tx2 = conn2.begin()
    conn2.execute(text("UPDATE isolation_test SET value = 100 WHERE id = 1"))
    tx2.commit()
    print("Session 2 updated value to 100 and committed")

    v2 = conn1.execute(text("SELECT value FROM isolation_test WHERE id = 1")).scalar()
    print(f"Session 1 second read: {v2}")

    if v1 != v2:
        print("=> non-repeatable read: YES (problem)")
    else:
        print("=> non-repeatable read: NO (correct for this level)")

    tx1.commit()
    conn1.close()
    conn2.close()


if __name__ == "__main__":
    demo("READ COMMITTED")
    demo("REPEATABLE READ")
