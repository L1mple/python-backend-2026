import os
from uuid import uuid4

from sqlalchemy import Boolean, Column, Integer, MetaData, Table, create_engine, func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema


def dirty_read(engine, balances, level):
    with engine.begin() as connection:
        connection.execute(balances.update().values(value=100))
    with engine.connect() as writer, engine.connect().execution_options(isolation_level=level) as reader:
        writer.execute(balances.update().values(value=200))
        value = reader.scalar(select(balances.c.value))
        assert value == 100
        print(f"Dirty read / {level}: writer has not committed 200, reader sees {value}")
        writer.rollback()


def repeated_read(engine, balances, level):
    with engine.begin() as connection:
        connection.execute(balances.update().values(value=100))
    with engine.connect().execution_options(isolation_level=level) as reader:
        first = reader.scalar(select(balances.c.value))
        with engine.begin() as writer:
            writer.execute(balances.update().values(value=200))
        second = reader.scalar(select(balances.c.value))
        assert (first, second) == (100, 200 if level == "READ COMMITTED" else 100)
        print(f"Non-repeatable read / {level}: {first} -> {second}")


def phantom_read(engine, balances, level):
    with engine.begin() as connection:
        connection.execute(balances.delete())
        connection.execute(balances.insert().values(id=1, value=100))
    query = select(func.count()).select_from(balances).where(balances.c.value >= 100)
    with engine.connect().execution_options(isolation_level=level) as reader:
        first = reader.scalar(query)
        with engine.begin() as writer:
            writer.execute(balances.insert().values(id=2, value=150))
        second = reader.scalar(query)
        assert (first, second) == (1, 2 if level == "READ COMMITTED" else 1)
        print(f"Phantom read / {level}: row count {first} -> {second}")


def write_skew(engine, doctors, level):
    with engine.begin() as connection:
        connection.execute(doctors.update().values(on_call=True))
    query = select(func.count()).select_from(doctors).where(doctors.c.on_call.is_(True))
    aborted = False
    with engine.connect().execution_options(isolation_level=level) as first, \
            engine.connect().execution_options(isolation_level=level) as second:
        assert first.scalar(query) == second.scalar(query) == 2
        try:
            first.execute(doctors.update().where(doctors.c.id == 1).values(on_call=False))
            second.execute(doctors.update().where(doctors.c.id == 2).values(on_call=False))
            first.commit()
            second.commit()
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) != "40001":
                raise
            aborted = True
            first.rollback()
            second.rollback()
    with engine.connect() as connection:
        remaining = connection.scalar(query)
    assert aborted == (level == "SERIALIZABLE")
    assert remaining == (1 if aborted else 0)
    print(f"Write skew / {level}: doctors on call = {remaining}, serialization failure = {aborted}")
    if aborted:
        # Retry the whole transaction, including the check, after SQLSTATE 40001.
        with engine.connect().execution_options(isolation_level=level) as retry:
            with retry.begin():
                if retry.scalar(query) > 1:
                    retry.execute(doctors.update().where(doctors.c.id == 2).values(on_call=False))
                assert retry.scalar(query) == 1
        print("Retry: one doctor remains on call, so the second cannot leave")


def main():
    url = os.getenv("DATABASE_URL", "postgresql+psycopg://shop:shop@127.0.0.1:7433/shop")
    engine = create_engine(url, connect_args={"options": "-c statement_timeout=10000"})
    if engine.dialect.name != "postgresql":
        raise RuntimeError("These examples use PostgreSQL")
    schema = "hw4_demo_" + uuid4().hex
    metadata = MetaData(schema=schema)
    balances = Table("balances", metadata, Column("id", Integer, primary_key=True), Column("value", Integer))
    doctors = Table("doctors", metadata, Column("id", Integer, primary_key=True), Column("on_call", Boolean))
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(balances.insert().values(id=1, value=100))
            connection.execute(doctors.insert(), [{"id": 1, "on_call": True}, {"id": 2, "on_call": True}])
        for level in ("READ UNCOMMITTED", "READ COMMITTED"):
            dirty_read(engine, balances, level)
        for level in ("READ COMMITTED", "REPEATABLE READ"):
            repeated_read(engine, balances, level)
        for level in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
            phantom_read(engine, balances, level)
        for level in ("REPEATABLE READ", "SERIALIZABLE"):
            write_skew(engine, doctors, level)
        print("All transaction examples passed")
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


if __name__ == "__main__":
    main()
