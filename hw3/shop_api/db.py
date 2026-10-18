"""Настройка SQLAlchemy: engine, sessionmaker, Base."""
import os

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://shop:shop@localhost:5432/shop",
)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""


async def get_session() -> AsyncSession:  # type: ignore[return]
    """FastAPI-зависимость: выдаёт сессию и закрывает её после запроса."""
    async with async_session_maker() as session:
        yield session
