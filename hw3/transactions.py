from uuid import uuid4

from sqlalchemy import text

from hw2.hw.shop_api.db import engine


def reset_rows(table):
    with engine.begin() as connection:
        connection.execute(text(f"DELETE FROM {table}"))
        connection.execute(text(f"INSERT INTO {table} (id, value) VALUES (1, 100)"))


def check_result(name, level, actual, expected):
    print(f"{name} | {level}: {actual} (expected {expected})")
    if actual != expected:
        raise AssertionError(f"Unexpected result for {name}: {actual}")


def dirty_read(table, level):
    reset_rows(table)
    with engine.connect().execution_options(isolation_level=level) as reader:
        with engine.connect() as writer:
            transaction = writer.begin()
            try:
                writer.execute(text(f"UPDATE {table} SET value = 200 WHERE id = 1"))
                before_rollback = reader.scalar(text(f"SELECT value FROM {table} WHERE id = 1"))
            finally:
                transaction.rollback()
            after_rollback = reader.scalar(text(f"SELECT value FROM {table} WHERE id = 1"))
    check_result("dirty read", level, (before_rollback, after_rollback), (100, 100))


def observe_committed_change(table, level, select_sql, change_sql):
    reset_rows(table)
    with engine.connect().execution_options(isolation_level=level) as reader:
        before = reader.scalar(text(select_sql))
        with engine.begin() as writer:
            writer.execute(text(change_sql))
        after = reader.scalar(text(select_sql))
    return before, after


def non_repeatable_read(table, level, expected):
    actual = observe_committed_change(
        table,
        level,
        f"SELECT value FROM {table} WHERE id = 1",
        f"UPDATE {table} SET value = 200 WHERE id = 1",
    )
    check_result("non-repeatable read", level, actual, expected)


def phantom_read(table, level, expected):
    actual = observe_committed_change(
        table,
        level,
        f"SELECT COUNT(*) FROM {table} WHERE value >= 100",
        f"INSERT INTO {table} (id, value) VALUES (2, 200)",
    )
    check_result("phantom read", level, actual, expected)


def main():
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Run with PostgreSQL")

    table = f"hw4_isolation_{uuid4().hex}"
    try:
        with engine.begin() as connection:
            connection.execute(text(
                f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, value INTEGER NOT NULL)"
            ))

        for level in ("READ UNCOMMITTED", "READ COMMITTED"):
            dirty_read(table, level)
        non_repeatable_read(table, "READ COMMITTED", (100, 200))
        non_repeatable_read(table, "REPEATABLE READ", (100, 100))
        phantom_read(table, "READ COMMITTED", (1, 2))
        phantom_read(table, "REPEATABLE READ", (1, 1))
        phantom_read(table, "SERIALIZABLE", (1, 1))
        print("isolation checks passed")
    finally:
        try:
            with engine.begin() as connection:
                connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()