"""
Демо аномалий транзакций на postgres.
Запуск (после docker compose up): python transactions/isolation.py

Две транзакции t1 и t2 идут "по очереди" в одном потоке:
t1 читает -> t2 что-то меняет -> t1 читает ещё раз.
"""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:password@localhost:7432/shop"
)
engine = create_engine(DATABASE_URL)


def reset():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS accounts"))
        conn.execute(text("CREATE TABLE accounts (id SERIAL PRIMARY KEY, name TEXT, balance INT)"))
        conn.execute(text("INSERT INTO accounts (name, balance) VALUES ('alice', 100), ('bob', 100)"))


def run(level, read_sql, change_sql, commit_change=True):
    """t1 читает два раза, между чтениями t2 меняет данные"""
    reset()
    t1 = engine.connect().execution_options(isolation_level=level)
    t2 = engine.connect()
    t1.begin()
    t2.begin()

    first = t1.execute(text(read_sql)).scalar()
    t2.execute(text(change_sql))
    if commit_change:
        t2.commit()
    second = t1.execute(text(read_sql)).scalar()

    t1.commit()
    t2.rollback()
    t1.close()
    t2.close()
    return first, second


def show(title, level, first, second, problem):
    happened = first != second
    print(f"\n{title} ({level})")
    print(f"  t1 прочитала: {first} -> {second}")
    print(f"  {problem}: {'ЕСТЬ' if happened else 'нет'}")


def dirty_read(level):
    # t2 меняет баланс, но НЕ коммитит
    first, second = run(
        level,
        "SELECT balance FROM accounts WHERE name = 'alice'",
        "UPDATE accounts SET balance = 999 WHERE name = 'alice'",
        commit_change=False,
    )
    show("Dirty read", level, first, second, "dirty read")


def non_repeatable_read(level):
    # t2 меняет баланс и коммитит
    first, second = run(
        level,
        "SELECT balance FROM accounts WHERE name = 'alice'",
        "UPDATE accounts SET balance = 200 WHERE name = 'alice'",
    )
    show("Non-repeatable read", level, first, second, "non-repeatable read")


def phantom_read(level):
    # t2 добавляет новую строку под условие t1 и коммитит
    first, second = run(
        level,
        "SELECT count(*) FROM accounts WHERE balance >= 100",
        "INSERT INTO accounts (name, balance) VALUES ('carol', 500)",
    )
    show("Phantom read", level, first, second, "phantom read")


def write_skew(level):
    """
    Правило: у каждого баланс может уйти в минус, но сумма должна быть >= 0.
    t1 и t2 одновременно проверяют сумму (200) и каждая списывает 150 у своего.
    По отдельности всё ок, вместе сумма уходит в -100.
    """
    reset()
    t1 = engine.connect().execution_options(isolation_level=level)
    t2 = engine.connect().execution_options(isolation_level=level)
    t1.begin()
    t2.begin()

    total = "SELECT sum(balance) FROM accounts"
    if t1.execute(text(total)).scalar() >= 150:
        t1.execute(text("UPDATE accounts SET balance = balance - 150 WHERE name = 'alice'"))
    if t2.execute(text(total)).scalar() >= 150:
        t2.execute(text("UPDATE accounts SET balance = balance - 150 WHERE name = 'bob'"))

    t1.commit()
    error = None
    try:
        t2.commit()
    except OperationalError as e:
        error = str(e.orig).splitlines()[0]
        t2.rollback()
    t1.close()
    t2.close()

    with engine.connect() as conn:
        result = conn.execute(text(total)).scalar()
    print(f"\nWrite skew / serialization anomaly ({level})")
    print(f"  итоговая сумма: {result}")
    print(f"  t2: {'ошибка: ' + error if error else 'закоммитилась'}")


if __name__ == "__main__":
    print("== Dirty read ==")
    # в postgres READ UNCOMMITTED работает как READ COMMITTED, поэтому dirty read не будет
    dirty_read("READ UNCOMMITTED")
    dirty_read("READ COMMITTED")

    print("\n== Non-repeatable read ==")
    non_repeatable_read("READ COMMITTED")
    non_repeatable_read("REPEATABLE READ")

    print("\n== Phantom read ==")
    # в postgres REPEATABLE READ уже защищает от фантомов (снапшот), поэтому показываем на READ COMMITTED
    phantom_read("READ COMMITTED")
    phantom_read("REPEATABLE READ")
    phantom_read("SERIALIZABLE")

    print("\n== Serializable ==")
    write_skew("REPEATABLE READ")
    write_skew("SERIALIZABLE")

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE accounts"))
