"""Подготовка БД для тестов.

Тесты ходят в приложение через TestClient без `with`: каждый запрос идёт
в новом event loop, а lifespan с созданием таблиц не запускается. Поэтому
здесь пул соединений отключается до импорта приложения, а таблицы
пересоздаются один раз перед всеми тестами.

Внимание: тесты очищают БД из DATABASE_URL.
"""

import asyncio
import os

os.environ.setdefault("DATABASE_POOL", "off")

from shop_api import db  # noqa: E402
from shop_api.models import Base  # noqa: E402


async def _recreate_schema() -> None:
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await db.engine.dispose()


def pytest_sessionstart(session) -> None:
    asyncio.run(_recreate_schema())
