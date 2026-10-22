import pytest
from fastapi.testclient import TestClient
from hw2.hw.shop_api.main import app
from hw2.hw.shop_api.store.database import engine
from hw2.hw.shop_api.store.orm import Base


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def item(client):
    return client.post("/item", json={"name": "Чай", "price": 150.0}).json()


@pytest.fixture()
def deleted_item(client, item):
    client.delete(f"/item/{item['id']}")
    return item


@pytest.fixture()
def items(client):
    return [
        client.post("/item", json={"name": f"Товар {price}", "price": price}).json()
        for price in [50.0, 100.0, 150.0, 200.0, 250.0]
    ]


@pytest.fixture()
def cart_id(client):
    return client.post("/cart").json()["id"]
