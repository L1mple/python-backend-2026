import pytest
from sqlalchemy import delete

from shop_api.database import SessionLocal
from shop_api.db_models import CartLineRecord, CartRecord, ItemRecord


def clear_tables():
    with SessionLocal.begin() as session:
        session.execute(delete(CartLineRecord))
        session.execute(delete(CartRecord))
        session.execute(delete(ItemRecord))


@pytest.fixture(autouse=True)
def clean_database():
    clear_tables()
    yield
    clear_tables()


@pytest.fixture
def item(client):
    response = client.post("/item", json={"name": "Milk", "price": 10.0})
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def cart(client):
    response = client.post("/cart")
    assert response.status_code == 201
    return response.json()
