import os
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from shop_api.models import Base

# 127.0.0.1, а не localhost: на Windows localhost сначала пробует IPv6 ::1,
# где Docker не слушает, и каждое подключение ждёт отказа около 2 секунд
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://shop:shop@127.0.0.1:5432/shop",
)

# Соединение asyncpg привязано к event loop, в котором его открыли.
# TestClient без `with` запускает каждый запрос в новом loop, и соединение
# из пула в следующем запросе падает с "attached to a different loop".
# Для такого запуска пул отключается: каждая сессия открывает своё соединение
# (так советует документация SQLAlchemy, раздел про несколько event loop)
_pool_options = {"poolclass": NullPool} if os.environ.get("DATABASE_POOL") == "off" else {}

engine = create_async_engine(DATABASE_URL, **_pool_options)

# expire_on_commit=False: после commit объекты остаются заполненными,
# и из них можно собрать ответ без повторного запроса в БД
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def create_schema() -> None:
    # Таблицы создаются при старте, если их ещё нет. Для учебного сервиса этого
    # хватает; когда схема начнёт меняться, нужны миграции (Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
