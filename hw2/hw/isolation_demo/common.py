import asyncio
from contextlib import asynccontextmanager
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import delete, insert, text

from shop_api.store.database import engine, session_factory
from shop_api.store.models import Item


class Isolation(StrEnum):
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


@asynccontextmanager
async def tx(level: Isolation):
    async with session_factory() as session:
        await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {level}"))
        try:
            yield session
        finally:
            await session.rollback()


def tag(scenario):
    return f"{scenario}-{uuid4().hex[:8]}"


async def new_item(name, price):
    async with session_factory() as session:
        item_id = await session.scalar(
            insert(Item).values(name=name, price=price).returning(Item.id)
        )
        await session.commit()
        return item_id


async def cleanup(prefix):
    async with session_factory() as session:
        await session.execute(delete(Item).where(Item.name.like(f"{prefix}%")))
        await session.commit()


def run(main):
    async def wrapper():
        try:
            await main()
        finally:
            await engine.dispose()

    asyncio.run(wrapper())
