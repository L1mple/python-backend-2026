import asyncio
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql+asyncpg://postgres:password@localhost:7432/hw4_db',
)

engine = create_async_engine(DATABASE_URL, echo=True, poolclass=NullPool)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


_schema_ready = False
_schema_lock = asyncio.Lock()


async def ensure_schema() -> None:
    global _schema_ready

    if _schema_ready:
        return

    async with _schema_lock:
        if _schema_ready:
            return

        import store.db.cart.models  # noqa
        import store.db.item.models  # noqa

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        _schema_ready = True


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    await ensure_schema()
    async with async_session_maker() as session:
        yield session
