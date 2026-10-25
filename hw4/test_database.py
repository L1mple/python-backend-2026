from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from shop_api.database import CartItemRow, CartRow, ItemRow, get_engine, make_engine
from shop_api.main import app


def test_data_survives_reconnecting_to_database():
    with TestClient(app) as client:
        item = client.post("/item", json={"name": uuid4().hex, "price": 12.5}).json()
        cart_id = client.post("/cart").json()["id"]
        assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 200
        expected = client.get(f"/cart/{cart_id}").json()
    engine = get_engine()
    engine.dispose()
    independent = make_engine(engine.url)
    try:
        with independent.connect() as connection:
            assert connection.scalar(select(ItemRow.name).where(ItemRow.id == item["id"])) == item["name"]
            assert connection.scalar(select(CartItemRow.quantity).where(
                CartItemRow.cart_id == cart_id, CartItemRow.item_id == item["id"],
            )) == 1
    finally:
        independent.dispose()
    with TestClient(app) as client:
        assert client.get(f"/item/{item['id']}").json() == item
        assert client.get(f"/cart/{cart_id}").json() == expected


def test_failed_transaction_rolls_back_all_changes():
    engine = get_engine()
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            cart_id = connection.execute(insert(CartRow)).inserted_primary_key[0]
            connection.execute(insert(CartItemRow).values(
                cart_id=cart_id, item_id=-1, quantity=1,
            ))
    with engine.connect() as connection:
        assert connection.scalar(select(CartRow.id).where(CartRow.id == cart_id)) is None


def test_concurrent_additions_do_not_lose_quantity():
    if get_engine().dialect.name != "mysql":
        pytest.skip("Row locks are checked against MySQL, not the SQLite test fallback")
    with TestClient(app) as client:
        item_id = client.post("/item", json={"name": uuid4().hex, "price": 3}).json()["id"]
        cart_id = client.post("/cart").json()["id"]
        path = f"/cart/{cart_id}/add/{item_id}"
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda _: client.post(path), range(32)))
        assert all(response.status_code == 200 for response in responses)
        cart = client.get(f"/cart/{cart_id}").json()
        assert cart["items"][0]["quantity"] == 32
        assert cart["price"] == 96
