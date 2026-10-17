import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

engine = create_engine(
    os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:password@localhost:7432/hw4_db",
    )
)

SERIALIZATION_FAILURE = "40001"


def prepare_table() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS accounts"))
        conn.execute(
            text("CREATE TABLE accounts (id SERIAL PRIMARY KEY, balance INT NOT NULL)")
        )
        conn.execute(text("INSERT INTO accounts (balance) VALUES (100), (200)"))


@contextmanager
def two_transactions(level: str):
    """Две независимые транзакции с одним уровнем изоляции на чистой таблице."""
    prepare_table()
    tx1 = engine.connect().execution_options(isolation_level=level)
    tx2 = engine.connect().execution_options(isolation_level=level)
    try:
        yield tx1, tx2
    finally:
        for tx in (tx1, tx2):
            tx.rollback()
            tx.close()


def read_balance(tx) -> int:
    return tx.execute(text("SELECT balance FROM accounts WHERE id = 1")).scalar_one()


def count_rows(tx) -> int:
    return tx.execute(text("SELECT count(*) FROM accounts")).scalar_one()


def insert_account(tx) -> None:
    tx.execute(text("INSERT INTO accounts (balance) VALUES (300)"))


def verdict(title: str, anomaly: bool, details: str) -> None:
    mark = "АНОМАЛИЯ ЕСТЬ " if anomaly else "аномалии нет  "
    print(f"[{mark}] {title}: {details}")


# --- сценарии ---------------------------------------------------------------

def check_dirty_read(level: str) -> None:
    with two_transactions(level) as (tx1, tx2):
        tx1.execute(text("UPDATE accounts SET balance = 0 WHERE id = 1"))  # без commit
        seen = read_balance(tx2)
        verdict(f"dirty read, {level}", seen != 100, f"tx2 увидел {seen}, в БД зафиксировано 100")


def check_non_repeatable_read(level: str) -> None:
    with two_transactions(level) as (tx1, tx2):
        first = read_balance(tx1)
        tx2.execute(text("UPDATE accounts SET balance = 500 WHERE id = 1"))
        tx2.commit()
        second = read_balance(tx1)
        verdict(
            f"non-repeatable read, {level}",
            first != second,
            f"tx1 прочитал {first}, потом {second}",
        )


def check_phantom_read(level: str) -> None:
    with two_transactions(level) as (tx1, tx2):
        first = count_rows(tx1)
        insert_account(tx2)
        tx2.commit()
        second = count_rows(tx1)
        verdict(
            f"phantom read, {level}",
            first != second,
            f"tx1 насчитал {first} строк, потом {second}",
        )


def check_serialization_conflict() -> None:
    """Обе транзакции считают строки и вставляют новую на основе прочитанного.
    Последовательного порядка, дающего такой результат, нет, поэтому
    Postgres на SERIALIZABLE должен отменить одну из них (SQLSTATE 40001)."""
    with two_transactions("SERIALIZABLE") as (tx1, tx2):
        count_rows(tx1)
        count_rows(tx2)
        insert_account(tx1)
        tx1.commit()
        try:
            insert_account(tx2)
            tx2.commit()
        except DBAPIError as exc:
            code = getattr(exc.orig, "sqlstate", None)
            verdict(
                "конфликт сериализации, SERIALIZABLE",
                False,
                f"tx2 отменена (sqlstate={code}, ожидали {SERIALIZATION_FAILURE})",
            )
        else:
            verdict("конфликт сериализации, SERIALIZABLE", True, "обе транзакции зафиксированы")


if __name__ == "__main__":
    print("== Dirty read ==")
    check_dirty_read("READ UNCOMMITTED")
    check_dirty_read("READ COMMITTED")

    print("\n== Non-repeatable read ==")
    check_non_repeatable_read("READ COMMITTED")
    check_non_repeatable_read("REPEATABLE READ")

    print("\n== Phantom read ==")
    check_phantom_read("READ COMMITTED")
    check_phantom_read("REPEATABLE READ")
    check_phantom_read("SERIALIZABLE")

    print("\n== Serializable ==")
    check_serialization_conflict()