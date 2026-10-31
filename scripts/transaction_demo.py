"""ДЗ4: два соединения PostgreSQL и проверяемые примеры изоляции транзакций.

Скрипт меняет только таблицу hw4_accounts.
Таблицы магазина не используются.
"""

import os

from sqlalchemy import create_engine, text


database_url = os.getenv(
    "TRANSACTION_DATABASE_URL",
    "postgresql+psycopg://student:student@127.0.0.1:15432/shop",
)
engine = create_engine(database_url)


def reset_accounts():
    with engine.begin() as db:
        db.execute(text("CREATE TABLE IF NOT EXISTS hw4_accounts (id INTEGER PRIMARY KEY, balance INTEGER NOT NULL)"))
        db.execute(text("DELETE FROM hw4_accounts"))
        db.execute(text("INSERT INTO hw4_accounts VALUES (1, 100)"))


def dirty_read(level):
    reset_accounts()
    with engine.connect().execution_options(isolation_level=level) as reader, engine.connect() as writer:
        writer.execute(text("UPDATE hw4_accounts SET balance = 200 WHERE id = 1"))
        # writer ещё не сделал commit. reader должен увидеть старые 100.
        value = reader.scalar(text("SELECT balance FROM hw4_accounts WHERE id = 1"))
        writer.rollback()
        assert value == 100, (level, value)
        print(f"Dirty read / {level}: read {value}; uncommitted 200 is invisible")


def repeated_read(level, expected):
    reset_accounts()
    with engine.connect().execution_options(isolation_level=level) as reader, engine.begin() as writer:
        first = reader.scalar(text("SELECT balance FROM hw4_accounts WHERE id = 1"))
        writer.execute(text("UPDATE hw4_accounts SET balance = 200 WHERE id = 1"))
        writer.commit()
        second = reader.scalar(text("SELECT balance FROM hw4_accounts WHERE id = 1"))
        assert (first, second) == expected, (level, first, second)
        print(f"Repeated read / {level}: {first} -> {second}")


def phantom_read(level, expected):
    reset_accounts()
    with engine.connect().execution_options(isolation_level=level) as reader, engine.begin() as writer:
        first = reader.scalar(text("SELECT COUNT(*) FROM hw4_accounts WHERE balance >= 100"))
        writer.execute(text("INSERT INTO hw4_accounts VALUES (2, 150)"))
        writer.commit()
        second = reader.scalar(text("SELECT COUNT(*) FROM hw4_accounts WHERE balance >= 100"))
        assert (first, second) == expected, (level, first, second)
        print(f"Phantom read / {level}: {first} -> {second} rows")


def main():
    if engine.dialect.name != "postgresql":
        raise SystemExit("These examples require PostgreSQL; set TRANSACTION_DATABASE_URL")
    dirty_read("READ UNCOMMITTED")
    dirty_read("READ COMMITTED")
    repeated_read("READ COMMITTED", (100, 200))
    repeated_read("REPEATABLE READ", (100, 100))
    phantom_read("READ COMMITTED", (1, 2))
    phantom_read("REPEATABLE READ", (1, 1))
    phantom_read("SERIALIZABLE", (1, 1))
    engine.dispose()
    print("All isolation checks passed")


if __name__ == "__main__":
    main()
