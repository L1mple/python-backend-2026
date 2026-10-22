from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from shop_api.database import Item
from shop_api.main import app
from shop_api import database


def test_data_survives_new_session(test_database):
    client = TestClient(app)
    item = client.post("/item", json={"name": "Persistent", "price": 12.5}).json()

    with database.SessionLocal() as session:
        stored = session.get(Item, item["id"])
        assert stored.name == "Persistent"
        assert stored.price == 12.5

    with TestClient(app) as another_client:
        assert another_client.get(f"/item/{item['id']}").json() == item


def test_concurrent_additions_are_not_lost(test_database):
    client = TestClient(app)
    item = client.post("/item", json={"name": "Concurrent", "price": 5}).json()
    cart_id = client.post("/cart").json()["id"]

    def add(_):
        response = client.post(f"/cart/{cart_id}/add/{item['id']}")
        assert response.status_code == 200

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(add, range(12)))

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["quantity"] == 12
    assert cart["price"] == 60


def test_failed_transaction_rolls_back(test_database):
    try:
        with database.SessionLocal.begin() as session:
            item = Item(name="Rollback", price=1)
            session.add(item)
            session.flush()
            item_id = item.id
            raise RuntimeError("simulate failure before commit")

    except RuntimeError:
        pass

    with database.SessionLocal() as session:
        assert session.get(Item, item_id) is None
