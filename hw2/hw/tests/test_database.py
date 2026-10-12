from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from shop_api import database, main
from shop_api.database import CartLineRecord, ItemRecord
from shop_api.models import Item, ItemData
from shop_api.store import ShopStore


def test_data_survives_app_restart_and_new_connections() -> None:
    with TestClient(main.app) as client:
        item = client.post("/item", json={"name": "Tea", "price": 10}).json()
        cart_id = client.post("/cart").json()["id"]
        client.post(f"/cart/{cart_id}/add/{item['id']}")
        expected = client.post(f"/cart/{cart_id}/add/{item['id']}").json()
        client.delete(f"/item/{item['id']}")

    # Lifespan disposes the pool; the next application opens new DB connections.
    with TestClient(main.app) as restarted:
        assert restarted.get(f"/item/{item['id']}").status_code == 404
        assert restarted.get("/item", params={"show_deleted": True}).json() == [
            {**item, "deleted": True}
        ]
        expected["price"] = 0.0
        expected["items"][0]["available"] = False
        assert restarted.get(f"/cart/{cart_id}").json() == expected
        assert restarted.post("/item", json={"name": "Coffee", "price": 20}).json()["id"] > item["id"]
    with Session(database.engine) as session:
        assert session.scalar(select(CartLineRecord.quantity)) == 2


def test_exception_after_insert_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    original = ShopStore.create_item

    def failing_insert(store: ShopStore, data: ItemData) -> Item:
        original(store, data)
        raise RuntimeError("Simulated failure after INSERT")

    monkeypatch.setattr(ShopStore, "create_item", failing_insert)
    with TestClient(main.app, raise_server_exceptions=False) as client:
        assert client.post("/item", json={"name": "Tea", "price": 10}).status_code == 500
    with Session(database.engine) as session:
        assert session.scalar(select(func.count()).select_from(ItemRecord)) == 0


def test_commit_failure_does_not_return_success() -> None:
    def fail_commit(session: Session) -> None:
        raise RuntimeError("Simulated COMMIT failure")

    event.listen(Session, "before_commit", fail_commit)
    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            assert client.post("/item", json={"name": "Tea", "price": 10}).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail_commit)
    with Session(database.engine) as session:
        assert session.scalar(select(func.count()).select_from(ItemRecord)) == 0


def test_concurrent_additions_do_not_lose_quantity(client: TestClient) -> None:
    if database.engine.dialect.name != "postgresql":
        pytest.skip("Row locks are checked by make test-hw4 against PostgreSQL")
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "Tea", "price": 10}).json()["id"]

    def add(_: int) -> int:
        return client.post(f"/cart/{cart_id}/add/{item_id}").status_code

    with ThreadPoolExecutor(max_workers=8) as workers:
        assert list(workers.map(add, range(24))) == [200] * 24
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["quantity"] == 24
    assert cart["price"] == 240
