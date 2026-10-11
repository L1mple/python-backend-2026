"""Show transaction isolation behavior supported by PostgreSQL."""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:password@localhost:7432/hw4_db",
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def start_transaction(isolation_level: str) -> tuple[Connection, object]:
    """Set isolation before the first statement, then begin the transaction."""
    connection = engine.connect().execution_options(isolation_level=isolation_level)
    return connection, connection.begin()


def reset_demo_table() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS isolation_demo "
                "(id INTEGER PRIMARY KEY, marker TEXT NOT NULL)"
            )
        )
        connection.execute(text("TRUNCATE TABLE isolation_demo"))
        connection.execute(
            text("INSERT INTO isolation_demo (id, marker) VALUES (1, 'committed'), (2, 'base')")
        )


def read_marker(connection: Connection) -> str:
    return connection.execute(
        text("SELECT marker FROM isolation_demo WHERE id = 1")
    ).scalar_one()


def dirty_read_attempt(isolation_level: str) -> str:
    reset_demo_table()
    writer, writer_transaction = start_transaction("READ COMMITTED")
    reader, reader_transaction = start_transaction(isolation_level)
    try:
        writer.execute(
            text("UPDATE isolation_demo SET marker = 'uncommitted' WHERE id = 1")
        )
        observed = read_marker(reader)
    finally:
        reader_transaction.rollback()
        reader.close()
        writer_transaction.rollback()
        writer.close()
    return observed


def non_repeatable_read(isolation_level: str) -> tuple[str, str]:
    reset_demo_table()
    reader, reader_transaction = start_transaction(isolation_level)
    writer, writer_transaction = start_transaction("READ COMMITTED")
    try:
        before = read_marker(reader)
        writer.execute(
            text("UPDATE isolation_demo SET marker = 'updated' WHERE id = 1")
        )
        writer_transaction.commit()
        after = read_marker(reader)
        reader_transaction.commit()
    except Exception:
        reader_transaction.rollback()
        writer_transaction.rollback()
        raise
    finally:
        reader.close()
        writer.close()
    return before, after


def range_rows(connection: Connection) -> list[tuple[int, str]]:
    rows = connection.execute(
        text("SELECT id, marker FROM isolation_demo WHERE id >= 10 ORDER BY id")
    ).all()
    return [(row.id, row.marker) for row in rows]


def phantom_read(isolation_level: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    reset_demo_table()
    reader, reader_transaction = start_transaction(isolation_level)
    writer, writer_transaction = start_transaction("READ COMMITTED")
    try:
        before = range_rows(reader)
        writer.execute(
            text("INSERT INTO isolation_demo (id, marker) VALUES (10, 'inserted')")
        )
        writer_transaction.commit()
        after = range_rows(reader)
        reader_transaction.commit()
    except Exception:
        reader_transaction.rollback()
        writer_transaction.rollback()
        raise
    finally:
        reader.close()
        writer.close()
    return before, after


def main() -> None:
    print("PostgreSQL transaction isolation observations")

    dirty_uncommitted = dirty_read_attempt("READ UNCOMMITTED")
    dirty_committed = dirty_read_attempt("READ COMMITTED")
    print("Dirty reads:")
    print(f"  READ UNCOMMITTED reader saw: {dirty_uncommitted!r}")
    print(f"  READ COMMITTED reader saw:   {dirty_committed!r}")
    print("  PostgreSQL treats READ UNCOMMITTED as READ COMMITTED; dirty reads are prevented.")

    rc_before, rc_after = non_repeatable_read("READ COMMITTED")
    rr_before, rr_after = non_repeatable_read("REPEATABLE READ")
    print("Non-repeatable reads:")
    print(f"  READ COMMITTED: {rc_before!r} -> {rc_after!r}")
    print(f"  REPEATABLE READ: {rr_before!r} -> {rr_after!r}")

    rr_phantoms_before, rr_phantoms_after = phantom_read("REPEATABLE READ")
    serial_before, serial_after = phantom_read("SERIALIZABLE")
    print("Phantom reads:")
    print(f"  REPEATABLE READ range: {rr_phantoms_before!r} -> {rr_phantoms_after!r}")
    print(f"  SERIALIZABLE range:    {serial_before!r} -> {serial_after!r}")
    print(
        "  PostgreSQL REPEATABLE READ keeps a stable snapshot and prevents phantoms, "
        "so this anomaly cannot be demonstrated at that level."
    )

    expected = {
        "dirty": dirty_uncommitted == dirty_committed == "committed",
        "non_repeatable": rc_before == "committed" and rc_after == "updated"
        and rr_before == rr_after == "committed",
        "phantom": rr_phantoms_before == rr_phantoms_after == []
        and serial_before == serial_after == [],
    }
    if not all(expected.values()):
        raise RuntimeError(f"Observed transaction behavior differed from PostgreSQL expectations: {expected}")


if __name__ == "__main__":
    main()
