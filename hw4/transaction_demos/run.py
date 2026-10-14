# сори за нейрослоп
import argparse
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from shop_api.database import DATABASE_URL


@contextmanager
def connections(engine, level):
    with engine.connect().execution_options(isolation_level=level) as a:
        with engine.connect().execution_options(isolation_level=level) as b:
            yield a, b


def reset(engine, table):
    with engine.begin() as connection:
        connection.execute(text(f"DELETE FROM {table}"))
        connection.execute(text(
            f"INSERT INTO {table} (id, price, available) "
            "VALUES (1, 100, TRUE), (2, 200, TRUE)"
        ))


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"  PASS: {message}")


def dirty(engine, table):
    for level in ("READ UNCOMMITTED", "READ COMMITTED"):
        reset(engine, table)
        print(f"\nDirty read / {level}")
        with connections(engine, level) as (a, b):
            a.execute(text(f"UPDATE {table} SET price = 999 WHERE id = 1"))
            print("  T1: UPDATE price = 999; no COMMIT")
            price = b.scalar(text(f"SELECT price FROM {table} WHERE id = 1"))
            print(f"  T2: SELECT price -> {price}")
            check(price == 100, "uncommitted price is invisible")
            a.rollback()
            print("  T1: ROLLBACK")
            price = b.scalar(text(f"SELECT price FROM {table} WHERE id = 1"))
            check(price == 100, "price is still 100 after rollback")
        print("  PostgreSQL: READ UNCOMMITTED has READ COMMITTED semantics.")


def nonrepeatable(engine, table):
    for level in ("READ COMMITTED", "REPEATABLE READ"):
        reset(engine, table)
        print(f"\nNon-repeatable read / {level}")
        with connections(engine, level) as (a, b):
            first = a.scalar(text(f"SELECT price FROM {table} WHERE id = 1"))
            print(f"  T1: first SELECT price -> {first}")
            b.execute(text(f"UPDATE {table} SET price = 150 WHERE id = 1"))
            b.commit()
            print("  T2: UPDATE price = 150; COMMIT")
            second = a.scalar(text(f"SELECT price FROM {table} WHERE id = 1"))
            print(f"  T1: second SELECT in the SAME transaction -> {second}")
            expected = 150 if level == "READ COMMITTED" else 100
            check(first == 100 and second == expected, f"observed prices: 100 -> {expected}")
            a.commit()


def phantom(engine, table):
    for level in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
        reset(engine, table)
        print(f"\nPhantom read / {level}")
        query = text(f"SELECT count(*) FROM {table} WHERE price >= 100")
        with connections(engine, level) as (a, b):
            first = a.scalar(query)
            print(f"  T1: first COUNT(price >= 100) -> {first}")
            b.execute(text(f"INSERT INTO {table} VALUES (3, 300, TRUE)"))
            b.commit()
            print("  T2: INSERT matching row; COMMIT")
            second = a.scalar(query)
            print(f"  T1: second COUNT in the SAME transaction -> {second}")
            expected = 3 if level == "READ COMMITTED" else 2
            check(first == 2 and second == expected, f"observed counts: 2 -> {expected}")
            a.commit()
        print("  PostgreSQL prevents phantom reads already at REPEATABLE READ.")


def write_skew(engine, table):
    count_query = text(f"SELECT count(*) FROM {table} WHERE available")
    for level in ("REPEATABLE READ", "SERIALIZABLE"):
        reset(engine, table)
        print(f"\nWrite skew / {level}")
        print("  Rule: at least one product must stay available.")
        failed = False
        with connections(engine, level) as (a, b):
            count_a = a.scalar(count_query)
            count_b = b.scalar(count_query)
            print(f"  T1 sees {count_a} available products; T2 sees {count_b}")
            check(count_a == count_b == 2, "both transactions initially permit removal")
            a.execute(text(f"UPDATE {table} SET available = FALSE WHERE id = 1"))
            b.execute(text(f"UPDATE {table} SET available = FALSE WHERE id = 2"))
            print("  T1 disables product 1; T2 disables product 2 (different rows)")
            a.commit()
            print("  T1: COMMIT")
            try:
                b.commit()
                print("  T2: COMMIT")
            except DBAPIError as exc:
                if getattr(exc.orig, "sqlstate", None) != "40001":
                    raise
                failed = True
                b.rollback()
                print("  T2: serialization_failure (SQLSTATE 40001); ROLLBACK")

        with engine.connect() as connection:
            remaining = connection.scalar(count_query)
        if level == "REPEATABLE READ":
            check(not failed and remaining == 0, "write skew reproduced: no available products")
        else:
            check(failed and remaining == 1, "conflicting transaction aborted; rule preserved")
            # Retry the WHOLE business operation using a fresh snapshot.
            with engine.connect().execution_options(isolation_level=level) as connection:
                with connection.begin():
                    count = connection.scalar(count_query)
                    if count > 1:
                        connection.execute(text(
                            f"UPDATE {table} SET available = FALSE WHERE id = 2"
                        ))
                    print(f"  T2 retry: sees {count}; refuses to disable the last product")
                    check(count == 1, "full retry rechecks the business rule")
            with engine.connect() as connection:
                check(connection.scalar(count_query) == 1, "one product remains after retry")


def main():
    demos = {
        "dirty": dirty,
        "nonrepeatable": nonrepeatable,
        "phantom": phantom,
        "write-skew": write_skew,
    }
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", default="all", choices=["all", *demos])
    args = parser.parse_args()
    engine = create_engine(
        DATABASE_URL,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=10000"},
    )
    # Names come only from our UUID, never from user-supplied SQL.
    schema = "transaction_demo_" + uuid4().hex
    table = f"{schema}.products"
    created = False
    try:
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
            connection.execute(text(
                f"CREATE TABLE {table} ("
                "id INTEGER PRIMARY KEY, price NUMERIC NOT NULL, available BOOLEAN NOT NULL)"
            ))
        created = True
        selected = demos.values() if args.scenario == "all" else [demos[args.scenario]]
        for demo in selected:
            demo(engine, table)
        print("\nAll selected scenarios passed.")
    finally:
        try:
            if created:
                with engine.begin() as connection:
                    connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
