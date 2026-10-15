from concurrent.futures import ThreadPoolExecutor
import os

from fastapi.testclient import TestClient
import pytest

from shop_api.main import app


@pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="Checks PostgreSQL row locks",
)
def test_parallel_additions():
    with TestClient(app) as client:
        item_id = client.post("/item", json={"name": "Book", "price": 10}).json()["id"]
        cart_id = client.post("/cart").json()["id"]

    def add_once(_):
        with TestClient(app) as client:
            return client.post(f"/cart/{cart_id}/add/{item_id}").status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(add_once, range(20)))
    assert statuses == [200] * 20
    with TestClient(app) as client:
        cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["quantity"] == 20
    assert cart["price"] == 200
