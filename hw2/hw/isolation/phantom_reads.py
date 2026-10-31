"""
Phantom read: транзакция дважды делает один и тот же запрос с условием и получает разное число строк, потому что между запросами другая транзакция вставила подходящую строку.

В Postgres REPEATABLE READ работает как snapshot isolation: транзакция видит снимок БД на момент старта и не замечает вставок, сделанных после. Поэтому phantom read в Postgres не воспроизводится даже на REPEATABLE READ.
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
        conn.execute(text("CREATE TABLE isolation_test (id serial primary key, value int)"))
        conn.execute(text("INSERT INTO isolation_test (value) VALUES (1)"))


def demo(level: str) -> None:
    setup()
    print(f"\n--- Level: {level} ---")

    conn1 = engine.connect().execution_options(isolation_level=level)
    tx1 = conn1.begin()
    n1 = conn1.execute(text("SELECT count(*) FROM isolation_test")).scalar()
    print(f"Session 1 first count:  {n1}")

    conn2 = engine.connect().execution_options(isolation_level=level)
    tx2 = conn2.begin()
    conn2.execute(text("INSERT INTO isolation_test (value) VALUES (999)"))
    tx2.commit()
    print("Session 2 inserted one more row and committed")

    n2 = conn1.execute(text("SELECT count(*) FROM isolation_test")).scalar()
    print(f"Session 1 second count: {n2}")

    if n1 != n2:
        print("=> phantom read: YES (problem)")
    else:
        print("=> phantom read: NO")

    tx1.commit()
    conn1.close()
    conn2.close()


if __name__ == "__main__":
    demo("REPEATABLE READ")
    demo("SERIALIZABLE")
