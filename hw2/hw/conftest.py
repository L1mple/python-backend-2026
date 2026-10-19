import asyncio
import os
from pathlib import Path

import pytest


def pytest_configure(config):
    """Для SQLite — удаляем файл, чтобы начать с чистого листа."""
    if os.getenv("DATABASE_URL"):
        return
    db = Path(__file__).parent / ".test.db"
    if db.exists():
        db.unlink()


@pytest.fixture(scope="session", autouse=True)
def _fresh_db():
    """
    Пересоздаём таблицы перед сессией тестов — для любой СУБД.

    `TestClient(app)` без `with` не запускает lifespan,
    поэтому таблицы в Postgres сами не появятся. Эта фикстура
    делает drop_all + create_all один раз перед тестами.
    NullPool в database.py гарантирует, что соединения
    из этого asyncio.run() не попадут в loop TestClient'а.
    """
    from shop_api.store.database import Base, engine

    async def recreate() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(recreate())
