import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from shop_api.main import app
from shop_api.store.database import session_factory
from shop_api.store.models import Cart, CartItem, Item


async def _wipe() -> None:
    async with session_factory() as session:
        for model in (CartItem, Cart, Item):
            await session.execute(delete(model))
        await session.commit()


@pytest.fixture
def client() -> TestClient:
    asyncio.run(_wipe())
    return TestClient(app)
