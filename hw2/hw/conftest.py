import asyncio

from sqlalchemy import delete

from shop_api.store.database import engine
from shop_api.store.models import Base, Cart, CartItem, Item


async def _prepare_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

        for model in (CartItem, Cart, Item):
            await connection.execute(delete(model))


def pytest_sessionstart(session) -> None:
    asyncio.run(_prepare_database())
