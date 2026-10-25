from __future__ import annotations

import os
from threading import Barrier, Thread

from sqlalchemy import create_engine, text

URL = os.getenv("DATABASE_URL", "postgresql+psycopg://shop:shop@localhost:5434/shop")
engine = create_engine(URL)


def run_two_transactions(level: str, statement: str, replacement: int = 2) -> tuple[object, object]:
    barrier = Barrier(2)
    values: list[object] = []

    def reader() -> None:
        with engine.connect() as conn:
            trans = conn.begin()
            values.append(conn.execute(text(statement)).scalar())
            barrier.wait()
            barrier.wait()
            values.append(conn.execute(text(statement)).scalar())
            trans.rollback()

    def writer() -> None:
        with engine.connect().execution_options(isolation_level=level) as conn:
            barrier.wait()
            conn.execute(text("UPDATE isolation_demo SET value = :value"), {"value": replacement})
            conn.commit()
            barrier.wait()

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS isolation_demo"))
        conn.execute(text("CREATE TABLE isolation_demo (value integer)"))
        conn.execute(text("INSERT INTO isolation_demo VALUES (1)"))
    first, second = Thread(target=reader), Thread(target=writer)
    first.start(); second.start(); first.join(); second.join()
    return values[0], values[1]


def run_dirty_read() -> tuple[object, object]:
    """Try to read an uncommitted update (PostgreSQL returns the old value)."""
    barrier = Barrier(2)
    values: list[object] = []

    def writer() -> None:
        with engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("UPDATE isolation_demo SET value = 2"))
            barrier.wait()
            barrier.wait()
            trans.rollback()

    def reader() -> None:
        with engine.connect().execution_options(isolation_level="READ UNCOMMITTED") as conn:
            barrier.wait()
            values.append(conn.execute(text("SELECT value FROM isolation_demo")).scalar())
            barrier.wait()

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS isolation_demo (value integer)"))
        conn.execute(text("DELETE FROM isolation_demo"))
        conn.execute(text("INSERT INTO isolation_demo VALUES (1)"))
    first, second = Thread(target=writer), Thread(target=reader)
    first.start(); second.start(); first.join(); second.join()
    return values[0], 2


def run_phantom(level: str) -> tuple[object, object]:
    barrier = Barrier(2)
    values: list[object] = []

    def reader() -> None:
        with engine.connect().execution_options(isolation_level=level) as conn:
            trans = conn.begin()
            query = text("SELECT count(*) FROM isolation_demo WHERE value > 1")
            values.append(conn.execute(query).scalar())
            barrier.wait(); barrier.wait()
            values.append(conn.execute(query).scalar())
            trans.rollback()

    def writer() -> None:
        with engine.connect() as conn:
            barrier.wait()
            conn.execute(text("INSERT INTO isolation_demo VALUES (3)"))
            conn.commit()
            barrier.wait()

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM isolation_demo"))
        conn.execute(text("INSERT INTO isolation_demo VALUES (1)"))
    first, second = Thread(target=reader), Thread(target=writer)
    first.start(); second.start(); first.join(); second.join()
    return values[0], values[1]


def main() -> None:
    dirty = run_dirty_read()
    print(f"dirty read (READ UNCOMMITTED; PostgreSQL maps it to READ COMMITTED): {dirty}")
    print(f"non-repeatable read (READ COMMITTED): {run_two_transactions('READ COMMITTED', 'SELECT value FROM isolation_demo')}")
    print(f"non-repeatable read prevented (REPEATABLE READ): {run_two_transactions('REPEATABLE READ', 'SELECT value FROM isolation_demo')}")
    print(f"phantom read (REPEATABLE READ; stable snapshot): {run_phantom('REPEATABLE READ')}")
    print(f"phantom reads prevented (SERIALIZABLE): {run_phantom('SERIALIZABLE')}")


if __name__ == "__main__":
    main()
