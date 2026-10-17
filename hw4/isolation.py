import os
from uuid import uuid4

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    Table,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema


def reset(engine, accounts, amounts=(100,)):
    with engine.begin() as connection:
        connection.execute(delete(accounts))
        connection.execute(
            insert(accounts),
            [
                {"id": index, "amount": amount}
                for index, amount in enumerate(amounts, start=1)
            ],
        )


def dirty_read(engine, accounts, isolation):
    reset(engine, accounts)
    with (
        engine.connect() as writer,
        engine.connect().execution_options(isolation_level=isolation) as reader,
    ):
        writer.begin()
        reader.begin()
        writer.execute(update(accounts).where(accounts.c.id == 1).values(amount=200))
        value = reader.scalar(select(accounts.c.amount).where(accounts.c.id == 1))
        writer.rollback()
        after_rollback = reader.scalar(
            select(accounts.c.amount).where(accounts.c.id == 1)
        )
        reader.rollback()
    assert value == after_rollback == 100, (isolation, value, after_rollback)
    print(
        f"{isolation}: незавершенное изменение 200 не видно, прочитано {value}; после отката {after_rollback}"
    )
    if isolation == "READ UNCOMMITTED":
        print(
            "В PostgreSQL READ UNCOMMITTED работает как READ COMMITTED: грязное чтение недоступно."
        )


def non_repeatable_read(engine, accounts, isolation):
    reset(engine, accounts)
    with engine.connect().execution_options(isolation_level=isolation) as reader:
        reader.begin()
        first = reader.scalar(select(accounts.c.amount).where(accounts.c.id == 1))
        with engine.begin() as writer:
            writer.execute(
                update(accounts).where(accounts.c.id == 1).values(amount=200)
            )
        second = reader.scalar(select(accounts.c.amount).where(accounts.c.id == 1))
        reader.rollback()
    expected = 200 if isolation == "READ COMMITTED" else 100
    assert first == 100 and second == expected, (isolation, first, second)
    print(f"{isolation}: повторное чтение строки {first} -> {second}")


def phantom_read(engine, accounts, isolation):
    reset(engine, accounts)
    query = select(func.count()).select_from(accounts).where(accounts.c.amount >= 100)
    with engine.connect().execution_options(isolation_level=isolation) as reader:
        reader.begin()
        first = reader.scalar(query)
        with engine.begin() as writer:
            writer.execute(insert(accounts).values(id=2, amount=200))
        second = reader.scalar(query)
        reader.rollback()
    expected = 2 if isolation == "READ COMMITTED" else 1
    assert first == 1 and second == expected, (isolation, first, second)
    print(f"{isolation}: число подходящих строк {first} -> {second}")
    if isolation == "REPEATABLE READ":
        print(
            "PostgreSQL предотвращает фантомы уже при REPEATABLE READ благодаря снимку данных."
        )


def write_skew(engine, accounts, isolation):
    reset(engine, accounts, (1, 1))
    query = select(func.sum(accounts.c.amount))
    rejected = False
    with (
        engine.connect().execution_options(isolation_level=isolation) as first,
        engine.connect().execution_options(isolation_level=isolation) as second,
    ):
        first.begin()
        second.begin()
        assert first.scalar(query) == second.scalar(query) == 2
        first.execute(update(accounts).where(accounts.c.id == 1).values(amount=0))
        first.commit()
        try:
            second.execute(update(accounts).where(accounts.c.id == 2).values(amount=0))
            second.commit()
        except DBAPIError as error:
            second.rollback()
            if getattr(error.orig, "sqlstate", None) != "40001":
                raise
            rejected = True
            print(f"{isolation}: вторая транзакция отклонена, SQLSTATE 40001")
    assert rejected == (isolation == "SERIALIZABLE"), isolation
    with engine.connect() as connection:
        remaining = connection.scalar(query)
    expected = 1 if rejected else 0
    assert remaining == expected, (isolation, remaining)
    print(
        f"{isolation}: активных записей осталось {remaining}; ограничение требует хотя бы одну"
    )
    if rejected:
        with (
            engine.connect().execution_options(isolation_level=isolation) as retry,
            retry.begin(),
        ):
            remaining = retry.scalar(query)
            if remaining > 1:
                retry.execute(
                    update(accounts).where(accounts.c.id == 2).values(amount=0)
                )
        with engine.connect() as connection:
            assert connection.scalar(query) == 1
        print(
            "Повтор всей второй транзакции видит одну активную запись и сохраняет ограничение."
        )


def main():
    url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://shop:shop@localhost:7432/shop"
    )
    engine = create_engine(
        url,
        connect_args={"options": "-c statement_timeout=5000 -c lock_timeout=3000"},
    )
    schema = "hw4_demo_" + uuid4().hex
    metadata = MetaData(schema=schema)
    accounts = Table(
        "accounts",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("amount", Integer, nullable=False),
    )
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        try:
            metadata.create_all(engine)
            for isolation in ("READ UNCOMMITTED", "READ COMMITTED"):
                dirty_read(engine, accounts, isolation)
            for isolation in ("READ COMMITTED", "REPEATABLE READ"):
                non_repeatable_read(engine, accounts, isolation)
            for isolation in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
                phantom_read(engine, accounts, isolation)
            for isolation in ("REPEATABLE READ", "SERIALIZABLE"):
                write_skew(engine, accounts, isolation)
            print("Все демонстрации завершились с ожидаемыми результатами.")
        finally:
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
