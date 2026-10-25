"""Run isolation experiments on two independent MySQL/InnoDB connections."""

import argparse
import os
from uuid import uuid4

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, delete, func, insert, select, update
from sqlalchemy.exc import OperationalError


def expect(actual, expected):
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def reset(engine, table):
    with engine.begin() as connection:
        connection.execute(delete(table))
        connection.execute(insert(table).values(id=1, value=10))


def dirty_read(engine, table, level):
    reset(engine, table)
    query = select(table.c.value).where(table.c.id == 1)
    with engine.connect() as writer, engine.connect().execution_options(isolation_level=level) as reader:
        writer.execute(update(table).where(table.c.id == 1).values(value=99))
        # Writer has not committed; reading 99 here is a dirty read.
        observed = reader.scalar(query)
        writer.rollback()
        reader.rollback()
        restored = reader.scalar(query)
        expect(observed, 99 if level == "READ UNCOMMITTED" else 10)
        expect(restored, 10)
        print(f"dirty read / {level}: during uncommitted UPDATE = {observed}, after ROLLBACK = {restored}")


def non_repeatable_read(engine, table, level):
    reset(engine, table)
    query = select(table.c.value).where(table.c.id == 1)
    with engine.connect().execution_options(isolation_level=level) as reader, engine.connect() as writer:
        before = reader.scalar(query)
        writer.execute(update(table).where(table.c.id == 1).values(value=99))
        writer.commit()
        after = reader.scalar(query)
        expect(before, 10)
        expect(after, 99 if level == "READ COMMITTED" else 10)
        reader.commit()
        expect(reader.scalar(query), 99)
        print(f"non-repeatable read / {level}: {before} -> {after}; new transaction = 99")


def phantom_read(engine, table, level):
    reset(engine, table)
    # A range predicate makes the experiment about a new matching row.
    query = select(func.count()).select_from(table).where(table.c.value >= 10)
    with engine.connect().execution_options(isolation_level=level) as reader, engine.connect() as writer:
        writer.exec_driver_sql("SET SESSION innodb_lock_wait_timeout = 1")
        writer.commit()
        before = reader.scalar(query)
        blocked = False
        try:
            writer.execute(insert(table).values(id=2, value=20))
            writer.commit()
        except OperationalError as error:
            writer.rollback()
            if error.orig.args[0] != 1205 or level != "SERIALIZABLE":
                raise
            blocked = True
        after = reader.scalar(query)
        expect(before, 1)
        expect(after, 2 if level == "READ COMMITTED" else 1)
        expect(blocked, level == "SERIALIZABLE")
        reader.commit()
        if blocked:
            # The same INSERT succeeds after the reader releases its range locks.
            writer.execute(insert(table).values(id=2, value=20))
            writer.commit()
        expect(reader.scalar(query), 2)
        explanation = "INSERT blocked by range lock" if blocked else "INSERT committed"
        print(f"phantom read / {level}: {before} -> {after}; {explanation}; new transaction = 2")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["all", "dirty", "non-repeatable", "phantom"], default="all")
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL", "mysql+pymysql://shop:shop@127.0.0.1:3307/shop?charset=utf8mb4")
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name != "mysql":
        raise SystemExit("These experiments require MySQL/InnoDB; set DATABASE_URL.")
    metadata = MetaData()
    # A unique table lets us run experiments without touching shop data.
    table = Table(
        f"isolation_demo_{uuid4().hex}", metadata,
        Column("id", Integer, primary_key=True), Column("value", Integer, nullable=False),
        mysql_engine="InnoDB",
    )
    try:
        metadata.create_all(engine)
        with engine.connect() as connection:
            print(f"MySQL {connection.exec_driver_sql('SELECT VERSION()').scalar_one()}")
        if args.scenario in ("all", "dirty"):
            for level in ("READ UNCOMMITTED", "READ COMMITTED"):
                dirty_read(engine, table, level)
        if args.scenario in ("all", "non-repeatable"):
            for level in ("READ COMMITTED", "REPEATABLE READ"):
                non_repeatable_read(engine, table, level)
        if args.scenario in ("all", "phantom"):
            for level in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
                phantom_read(engine, table, level)
        print("All selected experiments passed.")
    finally:
        metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    main()
