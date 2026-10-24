import os
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

# DATABASE_URL задан — PostgreSQL (docker / prod).
# Не задан — файловая SQLite через aiosqlite (локальные тесты и CI).
DATABASE_URL = os.getenv("DATABASE_URL")

SQLITE_PATH = Path(__file__).resolve().parents[2] / ".test.db"

if DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        # NullPool: в тестах init_db() вызывается из asyncio.run() (свой loop),
        # а сам TestClient работает в другом loop. Без NullPool asyncpg
        # тащит соединения из одного loop в другой и падает.
        poolclass=NullPool,
    )
    IS_SQLITE = False
else:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{SQLITE_PATH.as_posix()}",
        echo=False,
        poolclass=NullPool,
    )
    IS_SQLITE = True

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
