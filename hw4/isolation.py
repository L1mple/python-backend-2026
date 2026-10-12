"""Воспроизводимые опыты с двумя перекрывающимися транзакциями PostgreSQL."""

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError


@dataclass
class Result:
    scenario: str
    isolation: str
    before: int
    after: int
    anomaly: bool
    sqlstate: str | None = None


def reset(engine: Engine, table: str) -> None:
    """Вернуть отдельную таблицу опыта к двум счетам с балансом 100."""
    with engine.begin() as connection:
        connection.execute(text(f"DELETE FROM {table}"))
        connection.execute(text(f"INSERT INTO {table} VALUES (1, 100), (2, 100)"))


def read_demo(engine: Engine, table: str, scenario: str, isolation: str) -> Result:
    """Выполнить чтение A, изменение B и повторное чтение A без задержек."""
    reset(engine, table)
    query = (
        f"SELECT count(*) FROM {table} WHERE balance > 0"
        if scenario == "phantom_read"
        else f"SELECT balance FROM {table} WHERE id = 1"
    )
    with (
        engine.connect().execution_options(isolation_level=isolation) as reader,
        engine.connect() as writer,
        reader.begin(),
    ):
        before = reader.scalar(text(query))
        writer.begin()
        if scenario == "phantom_read":
            writer.execute(text(f"INSERT INTO {table} VALUES (3, 100)"))
        else:
            writer.execute(text(f"UPDATE {table} SET balance = 200 WHERE id = 1"))
        if scenario != "dirty_read":
            writer.commit()
        after = reader.scalar(text(query))
        if scenario == "dirty_read":
            writer.rollback()
    expected = scenario != "dirty_read" and isolation == "READ COMMITTED"
    assert (before != after) == expected, (scenario, isolation, before, after)
    return Result(scenario, isolation, before, after, before != after)


def write_skew(engine: Engine, table: str, isolation: str) -> Result:
    """Проверить правило «сумма >= 100» при снятии денег с разных счетов."""
    reset(engine, table)
    sqlstate = None
    with (
        engine.connect().execution_options(isolation_level=isolation) as first,
        engine.connect().execution_options(isolation_level=isolation) as second,
    ):
        first.begin()
        second.begin()
        before = first.scalar(text(f"SELECT sum(balance) FROM {table}"))
        assert second.scalar(text(f"SELECT sum(balance) FROM {table}")) == before == 200
        first.execute(text(f"UPDATE {table} SET balance = balance - 100 WHERE id = 1"))
        second.execute(text(f"UPDATE {table} SET balance = balance - 100 WHERE id = 2"))
        first.commit()
        try:
            second.commit()
        except DBAPIError as error:
            sqlstate = getattr(error.orig, "sqlstate", None)
            second.rollback()
            if sqlstate != "40001":
                raise
    with engine.connect() as connection:
        after = connection.scalar(text(f"SELECT sum(balance) FROM {table}"))
    if isolation == "SERIALIZABLE":
        assert sqlstate == "40001" and after == 100, (sqlstate, after)
    else:
        assert sqlstate is None and after == 0, (sqlstate, after)
    return Result("write_skew", isolation, before, after, after < 100, sqlstate)


def run_demos(url: str) -> dict[str, Any]:
    """Провести опыты в уникальной схеме и удалить только эту схему."""
    engine = create_engine(
        url,
        connect_args={"options": "-c statement_timeout=5000 -c lock_timeout=5000"},
    )
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise ValueError("Для опытов нужна PostgreSQL: задайте DATABASE_URL")
    schema = f"hw4_isolation_{uuid4().hex}"
    table = f"{schema}.accounts"
    try:
        with engine.begin() as connection:
            version = connection.scalar(text("SHOW server_version"))
            connection.execute(text(f"CREATE SCHEMA {schema}"))
            connection.execute(
                text(
                    f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, balance INTEGER NOT NULL)"
                )
            )
        results = []
        for scenario, levels in (
            ("dirty_read", ("READ UNCOMMITTED", "READ COMMITTED")),
            ("non_repeatable_read", ("READ COMMITTED", "REPEATABLE READ")),
            ("phantom_read", ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE")),
        ):
            results.extend(
                asdict(read_demo(engine, table, scenario, level)) for level in levels
            )
        results.extend(
            asdict(write_skew(engine, table, level))
            for level in ("REPEATABLE READ", "SERIALIZABLE")
        )
        return {"postgresql_version": version, "results": results}
    finally:
        try:
            with engine.begin() as connection:
                connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        finally:
            engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Сохранить результаты в JSON")
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL")
    if not url:
        parser.error("Задайте DATABASE_URL для PostgreSQL")
    report = run_demos(url)
    print(f"PostgreSQL {report['postgresql_version']}")
    for result in report["results"]:
        print(
            f"{result['scenario']:20} {result['isolation']:16} "
            f"{result['before']} -> {result['after']}  "
            f"anomaly={result['anomaly']} sqlstate={result['sqlstate']}"
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
