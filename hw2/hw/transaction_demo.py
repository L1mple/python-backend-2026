import argparse
import os
from collections.abc import Callable
from threading import Event, Thread
from time import sleep

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

DATABASE_URL = os.getenv(
    "DATABASE_URL", "mssql+pymssql://sa:ShopApi2026@localhost:1433/master"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def reset_data(database: Engine) -> None:
    with database.begin() as connection:
        connection.execute(
            text(
                """
                IF OBJECT_ID('transaction_demo', 'U') IS NULL
                CREATE TABLE transaction_demo (
                    id INT PRIMARY KEY,
                    price INT NOT NULL
                )
                """
            )
        )
        connection.execute(text("DELETE FROM transaction_demo"))
        connection.execute(
            text("INSERT INTO transaction_demo (id, price) VALUES (1, 100)")
        )


def read_price(connection: Connection) -> int:
    return connection.execute(
        text("SELECT price FROM transaction_demo WHERE id = 1")
    ).scalar_one()


def count_expensive(connection: Connection) -> int:
    return connection.execute(
        text("SELECT COUNT(*) FROM transaction_demo WHERE price >= 100")
    ).scalar_one()


def dirty_read(database: Engine) -> None:
    reset_data(database)
    writer = database.connect()
    reader = database.connect().execution_options(isolation_level="READ UNCOMMITTED")
    try:
        writer.begin()
        writer.execute(text("UPDATE transaction_demo SET price = 200 WHERE id = 1"))
        reader.begin()
        print(f"Прочитано до rollback: {read_price(reader)}")
        reader.rollback()
        writer.rollback()
    finally:
        reader.close()
        writer.close()


def no_dirty_read(database: Engine) -> None:
    reset_data(database)
    writer = database.connect()
    reader_started = Event()
    result: list[int] = []

    def read() -> None:
        with database.connect().execution_options(
            isolation_level="READ COMMITTED"
        ) as reader:
            with reader.begin():
                reader_started.set()
                result.append(read_price(reader))

    try:
        writer.begin()
        writer.execute(text("UPDATE transaction_demo SET price = 200 WHERE id = 1"))
        thread = Thread(target=read)
        thread.start()
        reader_started.wait()
        sleep(0.1)
        writer.rollback()
        thread.join()
        print(f"Прочитано после rollback незакоммиченной записи: {result[0]}")
    finally:
        writer.close()


def non_repeatable_read(database: Engine) -> None:
    reset_data(database)
    reader = database.connect().execution_options(isolation_level="READ COMMITTED")
    try:
        reader.begin()
        first = read_price(reader)
        with database.begin() as writer:
            writer.execute(text("UPDATE transaction_demo SET price = 200 WHERE id = 1"))
        second = read_price(reader)
        reader.rollback()
        print(f"Первое чтение: {first}; второе чтение: {second}")
    finally:
        reader.close()


def repeatable_read(database: Engine) -> None:
    reset_data(database)
    reader = database.connect().execution_options(isolation_level="REPEATABLE READ")
    writer_started = Event()
    writer_finished = Event()

    def update() -> None:
        with database.begin() as writer:
            writer_started.set()
            writer.execute(text("UPDATE transaction_demo SET price = 200 WHERE id = 1"))
        writer_finished.set()

    try:
        reader.begin()
        first = read_price(reader)
        thread = Thread(target=update)
        thread.start()
        writer_started.wait()
        sleep(0.1)
        second = read_price(reader)
        print(
            f"Первое чтение: {first}; второе чтение: {second}; "
            f"writer завершился: {writer_finished.is_set()}"
        )
        reader.commit()
        thread.join()
    finally:
        reader.close()


def phantom_read(database: Engine) -> None:
    reset_data(database)
    reader = database.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        reader.begin()
        first = count_expensive(reader)
        with database.begin() as writer:
            writer.execute(
                text("INSERT INTO transaction_demo (id, price) VALUES (2, 150)")
            )
        second = count_expensive(reader)
        reader.rollback()
        print(f"Количество до вставки: {first}; после вставки: {second}")
    finally:
        reader.close()


def no_phantom_read(database: Engine) -> None:
    reset_data(database)
    reader = database.connect().execution_options(isolation_level="SERIALIZABLE")
    writer_started = Event()
    writer_finished = Event()

    def insert() -> None:
        with database.begin() as writer:
            writer_started.set()
            writer.execute(
                text("INSERT INTO transaction_demo (id, price) VALUES (2, 150)")
            )
        writer_finished.set()

    try:
        reader.begin()
        first = count_expensive(reader)
        thread = Thread(target=insert)
        thread.start()
        writer_started.wait()
        sleep(0.1)
        second = count_expensive(reader)
        print(
            f"Количество до вставки: {first}; повторное чтение: {second}; "
            f"writer завершился: {writer_finished.is_set()}"
        )
        reader.commit()
        thread.join()
    finally:
        reader.close()


SCENARIOS: dict[str, Callable[[Engine], None]] = {
    "dirty": dirty_read,
    "no-dirty": no_dirty_read,
    "non-repeatable": non_repeatable_read,
    "repeatable": repeatable_read,
    "phantom": phantom_read,
    "no-phantom": no_phantom_read,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "scenario", choices=[*SCENARIOS, "all"], default="all", nargs="?"
    )
    args = parser.parse_args()
    scenarios = (
        SCENARIOS.items()
        if args.scenario == "all"
        else [(args.scenario, SCENARIOS[args.scenario])]
    )
    for name, scenario in scenarios:
        print(f"\n{name}:")
        scenario(engine)


if __name__ == "__main__":
    main()
