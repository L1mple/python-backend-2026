import argparse
import os
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


DEFAULT_DATABASE_URL = "postgresql+psycopg://shop:shop@localhost:5433/shop"


@contextmanager
def transaction(engine, schema, isolation_level="READ COMMITTED"):
    with engine.connect().execution_options(isolation_level=isolation_level) as connection:
        with connection.begin():
            connection.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
            connection.exec_driver_sql("SET LOCAL lock_timeout = '2s'")
            quoted_schema = engine.dialect.identifier_preparer.quote_identifier(schema)
            connection.exec_driver_sql(f"SET LOCAL search_path TO {quoted_schema}, pg_catalog")
            yield connection


@contextmanager
def transaction_pair(engine, schema, isolation_level):
    with (
        transaction(engine, schema, isolation_level) as first,
        transaction(engine, schema, isolation_level) as second,
    ):
        first_pid = first.connection.driver_connection.info.backend_pid
        second_pid = second.connection.driver_connection.info.backend_pid
        assert first_pid != second_pid, "T1 and T2 must use different connections"
        print(f"  T1 connection={first_pid}; T2 connection={second_pid}")
        yield first, second


def reset_accounts(engine, schema):
    with transaction(engine, schema) as connection:
        connection.execute(text("DELETE FROM accounts"))
        connection.execute(text("INSERT INTO accounts (id, balance) VALUES (1, 100)"))


def balance(connection):
    return connection.scalar(text("SELECT balance FROM accounts WHERE id = 1"))


def matching_accounts(connection):
    return connection.scalar(text("SELECT count(*) FROM accounts WHERE balance >= 100"))


def on_call_count(connection):
    return connection.scalar(text("SELECT count(*) FROM doctors WHERE on_call"))


def dirty_read(engine, schema, isolation_level):
    reset_accounts(engine, schema)
    print(f"\nDirty read / {isolation_level}")
    with transaction_pair(engine, schema, isolation_level) as (first, second):
        before = balance(first)
        print(f"  T1 SELECT balance: {before}")
        second.execute(text("UPDATE accounts SET balance = 200 WHERE id = 1"))
        print("  T2 UPDATE balance=200, without COMMIT")
        during = balance(first)
        print(f"  T1 SELECT balance while T2 is uncommitted: {during}")
        second.rollback()
        after = balance(first)
        print(f"  T2 ROLLBACK; T1 SELECT balance: {after}")
        assert (before, during, after) == (100, 100, 100)
    print("  PASS: no dirty read; PostgreSQL treats READ UNCOMMITTED as READ COMMITTED")


def non_repeatable_read(engine, schema, isolation_level):
    reset_accounts(engine, schema)
    print(f"\nNon-repeatable read / {isolation_level}")
    with transaction_pair(engine, schema, isolation_level) as (first, second):
        before = balance(first)
        print(f"  T1 SELECT balance: {before}")
        second.execute(text("UPDATE accounts SET balance = 200 WHERE id = 1"))
        second.commit()
        print("  T2 UPDATE balance=200; COMMIT")
        after = balance(first)
        print(f"  T1 SELECT balance again, in the same transaction: {after}")
        expected = 200 if isolation_level == "READ COMMITTED" else 100
        assert (before, after) == (100, expected)
    result = "reproduced" if before != after else "prevented"
    print(f"  PASS: non-repeatable read {result}")


def phantom_read(engine, schema, isolation_level):
    reset_accounts(engine, schema)
    print(f"\nPhantom read / {isolation_level}")
    with transaction_pair(engine, schema, isolation_level) as (first, second):
        before = matching_accounts(first)
        print(f"  T1 SELECT count(*) WHERE balance >= 100: {before}")
        second.execute(text("INSERT INTO accounts (id, balance) VALUES (2, 200)"))
        second.commit()
        print("  T2 INSERT account with balance=200; COMMIT")
        after = matching_accounts(first)
        print(f"  T1 repeat the same SELECT, in the same transaction: {after}")
        expected = 2 if isolation_level == "READ COMMITTED" else 1
        assert (before, after) == (1, expected)
    result = "reproduced" if before != after else "prevented"
    print(f"  PASS: phantom read {result}")
    if isolation_level == "REPEATABLE READ":
        print("  PostgreSQL REPEATABLE READ already prevents phantoms; this differs from the SQL minimum")


def write_skew(engine, schema, isolation_level):
    with transaction(engine, schema) as connection:
        connection.execute(text("DELETE FROM doctors"))
        connection.execute(text("INSERT INTO doctors (id, on_call) VALUES (1, true), (2, true)"))

    print(f"\nWrite skew / {isolation_level}")
    print("  Rule: at least one doctor must remain on call")
    failure = None
    with transaction_pair(engine, schema, isolation_level) as (first, second):
        first_count = on_call_count(first)
        second_count = on_call_count(second)
        print(f"  T1 SELECT on-call count: {first_count}; T2 SELECT on-call count: {second_count}")
        assert first_count == second_count == 2

        if first_count > 1:
            first.execute(text("UPDATE doctors SET on_call = false WHERE id = 1"))
        first.commit()
        print("  T1 takes doctor 1 off call; COMMIT")

        try:
            if second_count > 1:
                second.execute(text("UPDATE doctors SET on_call = false WHERE id = 2"))
            second.commit()
            print("  T2 takes doctor 2 off call using its earlier count; COMMIT")
        except DBAPIError as error:
            second.rollback()
            failure = getattr(error.orig, "sqlstate", None)
            if failure != "40001":
                raise
            print(f"  T2 rejected with SQLSTATE {failure}; ROLLBACK")

    with transaction(engine, schema) as connection:
        remaining = on_call_count(connection)

    if isolation_level == "REPEATABLE READ":
        assert failure is None
        assert remaining == 0
        print("  PASS: write skew reproduced; both committed, 0 doctors remain on call")
        return

    assert failure == "40001"
    assert remaining == 1
    with transaction(engine, schema, isolation_level) as connection:
        retry_count = on_call_count(connection)
        print(f"  T2 retry: NEW transaction, SELECT on-call count again: {retry_count}")
        if retry_count > 1:
            connection.execute(text("UPDATE doctors SET on_call = false WHERE id = 2"))
        else:
            print("  T2 retry: doctor 2 must stay on call; COMMIT without UPDATE")
        assert retry_count == 1

    with transaction(engine, schema) as connection:
        assert on_call_count(connection) == 1
    print("  PASS: serialization failure and a full transaction retry preserve the rule")


def run_demos(database_url):
    engine = create_engine(database_url, connect_args={"connect_timeout": 5})
    schema = f"hw4_isolation_{uuid4().hex}"
    quoted_schema = engine.dialect.identifier_preparer.quote_identifier(schema)
    created = False
    try:
        with transaction(engine, schema) as connection:
            version = connection.scalar(text("SELECT version()"))
            print(version)
            print(f"Temporary demonstration schema: {schema}")
            connection.exec_driver_sql(f"CREATE SCHEMA {quoted_schema}")
            connection.exec_driver_sql(
                f"CREATE TABLE {quoted_schema}.accounts (id INTEGER PRIMARY KEY, balance INTEGER NOT NULL)"
            )
            connection.exec_driver_sql(
                f"CREATE TABLE {quoted_schema}.doctors (id INTEGER PRIMARY KEY, on_call BOOLEAN NOT NULL)"
            )
        created = True

        for isolation_level in ("READ UNCOMMITTED", "READ COMMITTED"):
            dirty_read(engine, schema, isolation_level)
        for isolation_level in ("READ COMMITTED", "REPEATABLE READ"):
            non_repeatable_read(engine, schema, isolation_level)
        for isolation_level in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
            phantom_read(engine, schema, isolation_level)
        for isolation_level in ("REPEATABLE READ", "SERIALIZABLE"):
            write_skew(engine, schema, isolation_level)
        print("\nAll 9 isolation scenarios passed")
    finally:
        try:
            if created:
                with transaction(engine, schema) as connection:
                    connection.exec_driver_sql(f"DROP SCHEMA {quoted_schema} CASCADE")
                print(f"Removed demonstration schema: {schema}")
        finally:
            engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Demonstrate PostgreSQL transaction isolation with two connections")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    args = parser.parse_args()
    run_demos(args.database_url)


if __name__ == "__main__":
    main()
