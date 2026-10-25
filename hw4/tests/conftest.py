import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from hw4.lib import db
from hw4.lib.main import app


@pytest_asyncio.fixture
async def client():
    async with app.router.lifespan_context(app):
        assert db.pool is not None

        async with db.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "TRUNCATE cart_items, carts, items RESTART IDENTITY CASCADE"
                )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client
