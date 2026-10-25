import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://shop:shop@localhost:5432/shop",
)

engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def init_db_sync():
    """Синхронная инициализация БД для тестов."""
    sync_url = DATABASE_URL.replace("+asyncpg", "+psycopg2")
    sync_engine = create_engine(sync_url, poolclass=NullPool)
    SQLModel.metadata.create_all(sync_engine)
    sync_engine.dispose()


async def get_session():
    async with async_session() as session:
        yield session