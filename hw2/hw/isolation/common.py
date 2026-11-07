"""Общие части сценариев: таблица, транзакции с логом шагов, запуск и проверка."""

import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    func,
    literal_column,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from shop_api.db import DATABASE_URL

READ_UNCOMMITTED = "READ UNCOMMITTED"
READ_COMMITTED = "READ COMMITTED"
REPEATABLE_READ = "REPEATABLE READ"
SERIALIZABLE = "SERIALIZABLE"

# SQLSTATE ошибки сериализации: PostgreSQL откатывает транзакцию,
# и приложение должно повторить её целиком
SERIALIZATION_FAILURE = "40001"

metadata = MetaData()

# Отдельная таблица, чтобы сценарии не трогали данные магазина
items = Table(
    "isolation_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("price", Float, nullable=False),
    Column("deleted", Boolean, nullable=False, default=False),
)


async def reset_items(engine: AsyncEngine, rows: list[tuple[str, float]]) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
        await conn.execute(items.insert(), [{"name": name, "price": price} for name, price in rows])


async def drop_items(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)


async def read_committed_state(engine: AsyncEngine, query) -> Any:
    """Читает закоммиченное состояние отдельным соединением, после всех транзакций."""
    async with engine.connect() as conn:
        return await conn.scalar(query)


def is_serialization_failure(error: DBAPIError) -> bool:
    return getattr(error.orig, "sqlstate", None) == SERIALIZATION_FAILURE


class Tx:
    """Транзакция в своём соединении. Печатает каждый шаг, чтобы был виден порядок."""

    def __init__(self, name: str, conn: AsyncConnection) -> None:
        self.name = name
        self.conn = conn

    @classmethod
    async def start(cls, engine: AsyncEngine, name: str, level: str) -> "Tx":
        conn = await engine.connect()
        if level == READ_UNCOMMITTED:
            # Диалект asyncpg в SQLAlchemy этот уровень не принимает, поэтому
            # задаём его SQL-командой: она должна идти до первого запроса
            await conn.begin()
            await conn.execute(text(f"SET TRANSACTION ISOLATION LEVEL {level}"))
        else:
            # Уровень изоляции задаётся соединению до начала транзакции
            await conn.execution_options(isolation_level=level)
            await conn.begin()
        tx = cls(name, conn)
        # Первый запрос в транзакции: показываем, какой уровень реально выставлен.
        # На REPEATABLE READ и SERIALIZABLE снимок данных берётся именно здесь,
        # на первом запросе, а не на BEGIN
        actual = await conn.scalar(text("SELECT current_setting('transaction_isolation')"))
        tx.log(f"BEGIN ISOLATION LEVEL {level} (в БД: {actual})")
        return tx

    def log(self, message: str) -> None:
        print(f"  {self.name}: {message}")

    async def read(self, query, label: str) -> Any:
        value = await self.conn.scalar(query)
        self.log(f"{label} -> {value}")
        return value

    async def write(self, query, label: str) -> None:
        await self.conn.execute(query)
        self.log(label)

    async def commit(self) -> None:
        await self.conn.commit()
        self.log("COMMIT")

    async def rollback(self) -> None:
        await self.conn.rollback()
        self.log("ROLLBACK")

    async def close(self) -> None:
        await self.conn.close()


def price_of(item_id: int):
    return select(items.c.price).where(items.c.id == item_id)


def names_cheaper_than(price: float):
    # string_agg(name, ', ' ORDER BY id): названия одной строкой в постоянном порядке
    names = func.string_agg(items.c.name, aggregate_order_by(literal_column("', '"), items.c.id))
    return select(names).where(items.c.price < price)


def active_count():
    return select(func.count()).select_from(items).where(items.c.deleted.is_(False))


@dataclass(frozen=True)
class Case:
    level: str
    # Что ожидаем увидеть в PostgreSQL на этом уровне
    anomaly_expected: bool
    note: str = ""


@dataclass(frozen=True)
class Demo:
    title: str
    description: str
    # Сценарий возвращает True, если аномалия случилась
    scenario: Callable[[AsyncEngine, str], Awaitable[bool]]
    cases: list[Case]


async def run_demos(demos: list[Demo]) -> bool:
    engine = create_async_engine(DATABASE_URL)
    all_as_expected = True

    try:
        for demo in demos:
            print(f"\n=== {demo.title} ===")
            print(demo.description)

            for case in demo.cases:
                print(f"\n[{case.level}]")
                anomaly = await demo.scenario(engine, case.level)

                verdict = "есть" if anomaly else "нет"
                print(f"  Итог: {demo.title.lower()} {verdict}")
                if case.note:
                    print(f"  Почему: {case.note}")
                if anomaly != case.anomaly_expected:
                    all_as_expected = False
                    print("  !!! Не совпало с ожидаемым поведением PostgreSQL")
    finally:
        await drop_items(engine)
        await engine.dispose()

    print()
    print("Все сценарии совпали с ожиданием." if all_as_expected else "Есть расхождения, см. выше.")
    return all_as_expected


def main(demos: list[Demo]) -> None:
    sys.exit(0 if asyncio.run(run_demos(demos)) else 1)
