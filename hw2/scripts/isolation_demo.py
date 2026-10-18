"""Deterministic interleaving of two real PostgreSQL connections, no sleeps."""
import os
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

URL = os.getenv("DATABASE_URL", "postgresql+psycopg://shop:shop@localhost:5432/shop")


def value(connection):
    return connection.scalar(text("SELECT value FROM balances WHERE id = 1"))


def reset(engine):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE balances"))
        connection.execute(text("INSERT INTO balances VALUES (1, 100), (2, 100)"))


def dirty_read(engine, level):
    reset(engine)
    with engine.connect().execution_options(isolation_level=level) as reader, engine.connect() as writer:
        writer.execute(text("UPDATE balances SET value = 999 WHERE id = 1"))
        observed = value(reader)
        writer.rollback()
        assert observed == 100, (level, observed)
        print(f"{level}: uncommitted=999, reader={observed}, writer ROLLBACK; dirty read absent (PostgreSQL)")


def repeated_read(engine, level, phantom=False):
    reset(engine)
    query = text("SELECT count(*) FROM balances WHERE value >= 100") if phantom else text(
        "SELECT value FROM balances WHERE id = 1"
    )
    with engine.connect().execution_options(isolation_level=level) as reader:
        before = reader.scalar(query)
        with engine.begin() as writer:
            writer.execute(text("INSERT INTO balances VALUES (3, 100)" if phantom else
                                "UPDATE balances SET value = 200 WHERE id = 1"))
        after = reader.scalar(query)
        expected = (3 if phantom else 200) if level == "READ COMMITTED" else before
        assert after == expected, (level, before, after)
        print(f"{level}: {'phantom' if phantom else 'non-repeatable'} read: {before} -> {after}; "
              f"{'present' if before != after else 'absent'}")
        reader.commit()
    with engine.connect() as observer:
        assert observer.scalar(query) == (3 if phantom else 200)


def write_skew(engine, level):
    # Invariant: at least one account must retain a positive balance.
    reset(engine)
    with engine.connect().execution_options(isolation_level=level) as first, \
            engine.connect().execution_options(isolation_level=level) as second:
        query = text("SELECT count(*) FROM balances WHERE value > 0")
        assert first.scalar(query) == second.scalar(query) == 2
        first.execute(text("UPDATE balances SET value = 0 WHERE id = 1"))
        first.commit()
        rejected = False
        try:
            second.execute(text("UPDATE balances SET value = 0 WHERE id = 2"))
            second.commit()
        except DBAPIError as error:
            second.rollback()
            if getattr(error.orig, "sqlstate", None) != "40001":
                raise
            rejected = True
        assert rejected == (level == "SERIALIZABLE")
        if rejected:
            # Retry the WHOLE transaction: read again before deciding to write.
            assert second.scalar(query) == 1
            second.commit()  # Keep account 2 positive; invariant disallows the update.
        with engine.connect() as observer:
            remaining = observer.scalar(query)
        assert remaining == (1 if rejected else 0)
        print(f"{level}: write skew {'prevented (SQLSTATE 40001, full transaction retried)' if rejected else 'present'}; "
              f"positive accounts={remaining}")


def main():
    admin = create_engine(URL)
    if admin.dialect.name != "postgresql":
        raise RuntimeError("This demonstration requires PostgreSQL")
    schema = f"isolation_demo_{uuid4().hex}"
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(URL, connect_args={
        "options": f"-csearch_path={schema} -clock_timeout=5000 -cstatement_timeout=15000",
    })
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE balances (id integer PRIMARY KEY, value integer NOT NULL)"))
        for level in ("READ UNCOMMITTED", "READ COMMITTED"):
            dirty_read(engine, level)
        for level in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
            repeated_read(engine, level)
            repeated_read(engine, level, phantom=True)
        for level in ("REPEATABLE READ", "SERIALIZABLE"):
            write_skew(engine, level)
        print("All isolation checks passed.")
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


if __name__ == "__main__":
    main()
