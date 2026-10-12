"""Reproduce transaction anomalies on PostgreSQL using two real connections.

Each run uses its own schema and removes only that schema in the finally block.
Transactions overlap, but statements run in a fixed order, without sleep or races.
"""

import os
from uuid import uuid4

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://shop:shop@127.0.0.1:7432/shop")


def reset(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM demo_values"))
        connection.execute(text("INSERT INTO demo_values VALUES (1, 100), (2, 100)"))


def dirty_read(engine: Engine, level: str) -> None:
    reset(engine)
    print(f"\nDirty read / {level}")
    with (
        engine.connect().execution_options(isolation_level=level) as writer,
        engine.connect().execution_options(isolation_level=level) as reader,
    ):
        writer.execute(text("UPDATE demo_values SET value = 999 WHERE id = 1"))
        own = writer.scalar(text("SELECT value FROM demo_values WHERE id = 1"))
        before_rollback = reader.scalar(text("SELECT value FROM demo_values WHERE id = 1"))
        writer.rollback()
        after_rollback = reader.scalar(text("SELECT value FROM demo_values WHERE id = 1"))
        print(f"  A: UPDATE 100 -> {own}, without COMMIT")
        print(f"  B: SELECT -> {before_rollback}; A: ROLLBACK; B: SELECT -> {after_rollback}")
        assert own == 999
        assert before_rollback == after_rollback == 100
        print("  PASS: dirty read is absent (PostgreSQL maps READ UNCOMMITTED to READ COMMITTED)")


def non_repeatable_read(engine: Engine, level: str) -> None:
    reset(engine)
    print(f"\nNon-repeatable read / {level}")
    with (
        engine.connect().execution_options(isolation_level=level) as reader,
        engine.connect() as writer,
    ):
        before = reader.scalar(text("SELECT value FROM demo_values WHERE id = 1"))
        writer.execute(text("UPDATE demo_values SET value = 200 WHERE id = 1"))
        writer.commit()
        after = reader.scalar(text("SELECT value FROM demo_values WHERE id = 1"))
        print(f"  A: SELECT -> {before}; B: UPDATE -> 200, COMMIT; A: SELECT -> {after}")
        assert before == 100
        assert after == (200 if level == "READ COMMITTED" else 100)
        print(f"  PASS: non-repeatable read is {'present' if before != after else 'absent'}")
        reader.commit()
        assert reader.scalar(text("SELECT value FROM demo_values WHERE id = 1")) == 200
        print("  A: new transaction sees committed value 200")


def phantom_read(engine: Engine, level: str) -> None:
    reset(engine)
    print(f"\nPhantom read / {level}")
    query = text("SELECT count(*) FROM demo_values WHERE value >= 100")
    with (
        engine.connect().execution_options(isolation_level=level) as reader,
        engine.connect() as writer,
    ):
        before = reader.scalar(query)
        writer.execute(text("INSERT INTO demo_values VALUES (3, 100)"))
        writer.commit()
        after = reader.scalar(query)
        print(f"  A: COUNT -> {before}; B: INSERT matching row, COMMIT; A: COUNT -> {after}")
        assert before == 2
        assert after == (3 if level == "READ COMMITTED" else 2)
        print(f"  PASS: phantom read is {'present' if before != after else 'absent'}")
        reader.commit()
        assert reader.scalar(query) == 3
        print("  A: new transaction sees 3 rows")


def serialization_anomaly(engine: Engine, level: str) -> None:
    reset(engine)
    print(f"\nSerialization anomaly (write skew) / {level}")
    print("  Rule: total balance must stay >= 100; withdraw 100 only when total >= 200")
    query = text("SELECT sum(value) FROM demo_values")
    aborted = False
    with (
        engine.connect().execution_options(isolation_level=level) as first,
        engine.connect().execution_options(isolation_level=level) as second,
    ):
        first_total, second_total = first.scalar(query), second.scalar(query)
        assert first_total == second_total == 200
        print(f"  A: total = {first_total}; B: total = {second_total}, before either COMMIT")
        first.execute(text("UPDATE demo_values SET value = value - 100 WHERE id = 1"))
        second.execute(text("UPDATE demo_values SET value = value - 100 WHERE id = 2"))
        first.commit()
        try:
            second.commit()
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) != "40001":
                raise
            second.rollback()
            aborted = True
            print("  B: PostgreSQL rejected COMMIT with SQLSTATE 40001 (serialization_failure)")

    with engine.connect() as connection:
        total = connection.scalar(query)
    if level == "REPEATABLE READ":
        assert not aborted and total == 0
        print("  PASS: both transactions committed, total = 0; the rule was violated")
    else:
        assert aborted and total == 100
        print("  PASS: one transaction rolled back, total = 100; the rule was preserved")
        # Retry the WHOLE transaction, including the read and business decision.
        with engine.connect().execution_options(isolation_level=level) as retry:
            current_total = retry.scalar(query)
            if current_total >= 200:
                retry.execute(text("UPDATE demo_values SET value = value - 100 WHERE id = 2"))
            retry.commit()
            assert current_total == 100
            assert retry.scalar(query) == 100
            print("  B: retry reads total = 100 and refuses the withdrawal; rule still holds")


def main() -> None:
    schema = f"hw4_demo_{uuid4().hex}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "options": f"-c search_path={schema} -c statement_timeout=5000 -c lock_timeout=5000"
        },
    )
    try:
        with engine.begin() as connection:
            print(f"PostgreSQL {connection.scalar(text('SHOW server_version'))}")
            connection.execute(text(f"CREATE SCHEMA {schema}"))
            connection.execute(
                text("CREATE TABLE demo_values (id integer PRIMARY KEY, value integer NOT NULL)")
            )
        with engine.connect() as first, engine.connect() as second:
            first_pid = first.scalar(text("SELECT pg_backend_pid()"))
            second_pid = second.scalar(text("SELECT pg_backend_pid()"))
            assert first_pid != second_pid
            print("Two independent PostgreSQL connections confirmed")
        for level in ("READ UNCOMMITTED", "READ COMMITTED"):
            dirty_read(engine, level)
        for level in ("READ COMMITTED", "REPEATABLE READ"):
            non_repeatable_read(engine, level)
        for level in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
            phantom_read(engine, level)
        for level in ("REPEATABLE READ", "SERIALIZABLE"):
            serialization_anomaly(engine, level)
        print("\nALL 9 SCENARIOS PASSED")
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        engine.dispose()


if __name__ == "__main__":
    main()
