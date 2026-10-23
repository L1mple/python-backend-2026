import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://shop:shop@localhost:5432/shop"
)

engine = create_engine(DATABASE_URL)


def reset() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS accounts"))
        conn.execute(
            text("CREATE TABLE accounts (id int PRIMARY KEY, balance int NOT NULL)")
        )
        conn.execute(text("INSERT INTO accounts VALUES (1, 100), (2, 100)"))


def connect(level: str):
    return engine.connect().execution_options(isolation_level=level)


def balance(conn) -> int:
    return conn.execute(text("SELECT balance FROM accounts WHERE id = 1")).scalar_one()


def result(level: str, anomaly: str, happened: bool, details: str) -> None:
    print(f"[{level:<16}] {anomaly:<20} {'ЕСТЬ' if happened else 'НЕТ':<5} ({details})")


def dirty_read(level: str) -> None:
    reset()
    with connect(level) as t1, connect(level) as t2:
        t2.execute(text("UPDATE accounts SET balance = 0 WHERE id = 1"))
        seen = balance(t1)
        t2.rollback()
        t1.commit()
    result(
        level,
        "dirty read",
        seen == 0,
        f"T1 прочитал {seen}, незакоммиченное значение 0",
    )


def non_repeatable_read(level: str) -> None:
    reset()
    with connect(level) as t1, connect(level) as t2:
        first = balance(t1)
        t2.execute(text("UPDATE accounts SET balance = 50 WHERE id = 1"))
        t2.commit()
        second = balance(t1)
        t1.commit()
    result(
        level,
        "non-repeatable read",
        first != second,
        f"T1 прочитал {first}, потом {second}",
    )


def phantom_read(level: str) -> None:
    reset()
    count_query = text("SELECT count(*) FROM accounts WHERE balance >= 100")
    with connect(level) as t1, connect(level) as t2:
        first = t1.execute(count_query).scalar_one()
        t2.execute(text("INSERT INTO accounts VALUES (3, 100)"))
        t2.commit()
        second = t1.execute(count_query).scalar_one()
        t1.commit()
    result(
        level,
        "phantom read",
        first != second,
        f"T1 насчитал {first} строки, потом {second}",
    )


def serialization_anomaly(level: str) -> None:
    reset()
    sum_query = text("SELECT sum(balance) FROM accounts")
    withdraw = text("UPDATE accounts SET balance = balance - 150 WHERE id = :id")
    with connect(level) as t1, connect(level) as t2:
        assert t1.execute(sum_query).scalar_one() - 150 >= 0
        assert t2.execute(sum_query).scalar_one() - 150 >= 0
        t1.execute(withdraw, {"id": 1})
        t2.execute(withdraw, {"id": 2})
        t1.commit()
        try:
            t2.commit()
            rejected = False
        except DBAPIError:
            rejected = True

    with engine.connect() as conn:
        total = conn.execute(sum_query).scalar_one()
    details = (
        "T2 отменена с ошибкой сериализации"
        if rejected
        else "обе транзакции закоммичены"
    )
    result(level, "serialization", total < 0, f"{details}, итоговая сумма {total}")


if __name__ == "__main__":
    print(
        "В PostgreSQL READ UNCOMMITTED работает как READ COMMITTED, поэтому dirty read не воспроизводится."
    )
    print("REPEATABLE READ в PostgreSQL — это snapshot isolation: фантомов на нём нет,")
    print(
        "поэтому phantom read показан на READ COMMITTED, а на REPEATABLE READ — аномалия сериализации (write skew).\n"
    )

    dirty_read("READ UNCOMMITTED")
    dirty_read("READ COMMITTED")

    non_repeatable_read("READ COMMITTED")
    non_repeatable_read("REPEATABLE READ")

    phantom_read("READ COMMITTED")
    phantom_read("REPEATABLE READ")
    phantom_read("SERIALIZABLE")

    serialization_anomaly("REPEATABLE READ")
    serialization_anomaly("SERIALIZABLE")
