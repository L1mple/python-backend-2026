import pytest
from fastapi.testclient import TestClient
from shop_api.main import app, carts, chat_rooms, items


@pytest.fixture(autouse=True)
def reset_storage():
    items.clear()
    carts.clear()
    chat_rooms.connections.clear()
    yield
    items.clear()
    carts.clear()
    chat_rooms.connections.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
