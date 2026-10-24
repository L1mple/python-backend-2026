import asyncio
import os

import asyncpg
import pytest
from sqlalchemy.engine import make_url

# По умолчанию тесты гоняются на in-memory реализации хранилища и не требуют БД.
# STORAGE_BACKEND=postgres pytest ... — тот же набор на PostgreSQL в отдельной базе shop_test.
os.environ.setdefault('STORAGE_BACKEND', 'memory')
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://shop:shop@localhost:5432/shop_test')

from shop_api.config import DATABASE_URL, STORAGE_BACKEND  # noqa: E402
from shop_api.database import create_engine  # noqa: E402
from shop_api.storage.tables import Base  # noqa: E402


async def _create_database_if_missing() -> None:
    url = make_url(DATABASE_URL)
    conn = await asyncpg.connect(
        host=url.host, port=url.port, user=url.username, password=url.password, database='postgres',
    )
    try:
        exists = await conn.fetchval('SELECT 1 FROM pg_database WHERE datname = $1', url.database)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


async def _drop_tables() -> None:
    engine = create_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope='session', autouse=True)
def clean_database():
    if STORAGE_BACKEND != 'postgres':
        yield
        return

    asyncio.run(_create_database_if_missing())
    asyncio.run(_drop_tables())
    yield
    asyncio.run(_drop_tables())
