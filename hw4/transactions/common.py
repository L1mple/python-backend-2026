"""Общие хелперы для демонстрации аномалий транзакций.

Каждая демонстрация открывает два независимых соединения (T1 и T2) к Postgres,
выставляет им уровень изоляции через SQLAlchemy и пошагово чередует их запросы.
Работаем с таблицей `items` приложения, но только со строками с префиксом DEMO_PREFIX.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from shop_api.database import create_engine
from shop_api.storage.tables import Base, ItemRecord

DEMO_PREFIX = 'isolation-demo'

engine = create_engine()


async def reset_demo_items(*items: tuple[str, float]) -> list[int]:
    """Пересоздаёт демо-товары и возвращает их id."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(delete(ItemRecord).where(ItemRecord.name.startswith(DEMO_PREFIX)))
        result = await conn.execute(
            insert(ItemRecord).returning(ItemRecord.id),
            [{'name': f'{DEMO_PREFIX}: {name}', 'price': price} for name, price in items],
        )
        return list(result.scalars())


async def cleanup() -> None:
    async with engine.begin() as conn:
        await conn.execute(delete(ItemRecord).where(ItemRecord.name.startswith(DEMO_PREFIX)))
    await engine.dispose()


@asynccontextmanager
async def transaction(isolation_level: str) -> AsyncGenerator[AsyncConnection]:
    """Соединение с заданным уровнем изоляции; транзакцию явно завершает вызывающий код."""
    async with engine.connect() as conn:
        if isolation_level == 'READ UNCOMMITTED':
            # SQLAlchemy не даёт выставить этот уровень для Postgres, т.к. он фактически
            # не поддерживается. Ставим его напрямую SQL-командой: Postgres её примет.
            await conn.begin()
            await conn.execute(text('SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED'))
        else:
            conn = await conn.execution_options(isolation_level=isolation_level)
            await conn.begin()
        actual = await conn.scalar(text('SHOW transaction_isolation'))
        print(f'  (соединение: transaction_isolation = {actual})')
        yield conn
        if conn.in_transaction():
            await conn.rollback()


async def get_price(conn: AsyncConnection, item_id: int) -> float | None:
    return await conn.scalar(select(ItemRecord.price).where(ItemRecord.id == item_id))


async def count_demo_items(conn: AsyncConnection, **filters) -> int | None:
    stmt = select(func.count()).select_from(ItemRecord).where(ItemRecord.name.startswith(DEMO_PREFIX))
    if 'min_price' in filters:
        stmt = stmt.where(ItemRecord.price >= filters['min_price'])
    if 'deleted' in filters:
        stmt = stmt.where(ItemRecord.deleted.is_(filters['deleted']))
    return await conn.scalar(stmt)


def is_serialization_failure(exc: DBAPIError) -> bool:
    return getattr(exc.orig, 'sqlstate', None) == '40001'


def header(title: str) -> None:
    print(f'\n{"=" * 78}\n{title}\n{"=" * 78}')


def t1(message: str) -> None:
    print(f'  [T1] {message}')


def t2(message: str) -> None:
    print(f'  {"":38}[T2] {message}')


def verdict(anomaly: str, happened: bool) -> None:
    mark = 'ДА  ✗' if happened else 'НЕТ ✓'
    print(f'  --> {anomaly}: {mark}')
