import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/shop_db"
)

_engine = None
AsyncSessionLocal = None


def _ensure_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, echo=False)
    return _engine


def __getattr__(name):
    if name == "engine":
        return _ensure_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():  # pragma: no cover
    return ["DATABASE_URL", "_engine", "_ensure_engine", "_ensure_session_local", "Base", "get_db", "engine", "AsyncSessionLocal"]


def _ensure_session_local():
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        _ensure_engine()
        AsyncSessionLocal = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    return AsyncSessionLocal


class Base(DeclarativeBase):
    pass


async def get_db():
    _ensure_session_local()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
