import os
import socket
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_URL = f"postgresql+asyncpg://shop:shop@{POSTGRES_HOST}:{POSTGRES_PORT}/shop"
SQLITE_URL = "sqlite+aiosqlite:///shop.db"


def postgres_is_reachable(timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((POSTGRES_HOST, POSTGRES_PORT), timeout):
            return True
    except OSError:
        return False


def resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    return POSTGRES_URL if postgres_is_reachable() else SQLITE_URL


database_url = resolve_database_url()

engine = create_async_engine(database_url, poolclass=NullPool)

session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


SessionDependency = Annotated[AsyncSession, Depends(get_session)]
