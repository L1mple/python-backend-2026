from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient
from shop_api import main
from shop_api.database import CartPosition, CartRow, ItemRow
from shop_api.models import ItemInput
from shop_api.store import Shop
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError


def test_new_store_reconnects_to_persisted_cart(tmp_path):
    url = f"sqlite:///{tmp_path / 'shop.db'}"
    first = Shop(url)
    item = first.create_item(ItemInput(name="Milk", price=2.5))
    cart_id = first.create_cart()
    first.add_item(cart_id, item.id)
    first.engine.dispose()
    second = Shop(url)
    try:
        cart = second.get_cart(cart_id)
        assert cart.price == 2.5
        assert cart.items[0].id == item.id
        assert cart.items[0].quantity == 1
    finally:
        second.engine.dispose()


def test_reconnect_keeps_deleted_positions_and_current_prices(isolated_shop):
    shop = isolated_shop
    milk = shop.create_item(ItemInput(name="Milk", price=2))
    bread = shop.create_item(ItemInput(name="Bread", price=3))
    cart_id = shop.create_cart()
    shop.add_item(cart_id, bread.id)
    shop.add_item(cart_id, milk.id)
    shop.delete_item(bread.id)
    shop.engine.dispose()
    second = Shop(shop.engine.url)
    try:
        cart = second.get_cart(cart_id)
        assert cart.price == 2
        assert [(item.id, item.available) for item in cart.items] == [
            (bread.id, False),
            (milk.id, True),
        ]
        second.replace_item(milk.id, ItemInput(name="Fresh milk", price=4))
        assert shop.get_cart(cart_id).price == 4
    finally:
        second.engine.dispose()


@pytest.mark.parametrize("initial_quantity", [0, 1])
def test_failed_add_rolls_back_written_quantity(
    isolated_shop, monkeypatch, initial_quantity
):
    shop = isolated_shop
    item = shop.create_item(ItemInput(name="Milk", price=2))
    cart_id = shop.create_cart()
    for _ in range(initial_quantity):
        shop.add_item(cart_id, item.id)

    def fail_response(session, ids):
        raise RuntimeError("Response failed after the upsert")

    with monkeypatch.context() as patch:
        patch.setattr(shop, "_carts", fail_response)
        with pytest.raises(RuntimeError, match="after the upsert"):
            shop.add_item(cart_id, item.id)
    assert (
        sum(position.quantity for position in shop.get_cart(cart_id).items)
        == initial_quantity
    )
    assert shop.add_item(cart_id, item.id).items[0].quantity == initial_quantity + 1


@pytest.mark.parametrize("price", [-1, float("inf"), float("-inf"), float("nan")])
def test_database_rejects_invalid_prices_and_rolls_back(isolated_shop, price):
    with pytest.raises(IntegrityError), isolated_shop.engine.begin() as connection:
        connection.execute(insert(ItemRow).values(name="Valid", price=1, deleted=False))
        connection.execute(
            insert(ItemRow).values(name="Invalid", price=price, deleted=False)
        )
    assert isolated_shop.list_items(0, 10, None, None, True) == []


@pytest.mark.parametrize("invalid", ["quantity", "cart_fk", "item_fk", "duplicate"])
def test_database_rejects_invalid_cart_positions(isolated_shop, invalid):
    shop = isolated_shop
    item = shop.create_item(ItemInput(name="Milk", price=2))
    cart_id = shop.create_cart()
    shop.add_item(cart_id, item.id)
    values = {"cart_id": cart_id, "item_id": item.id, "quantity": 1}
    if invalid == "quantity":
        values["quantity"] = 0
        second = shop.create_item(ItemInput(name="Bread", price=3))
        values["item_id"] = second.id
    elif invalid == "cart_fk":
        values["cart_id"] = 999999
    elif invalid == "item_fk":
        values["item_id"] = 999999
    with pytest.raises(IntegrityError), shop.engine.begin() as connection:
        connection.execute(insert(CartPosition).values(**values))
    assert shop.get_cart(cart_id).items[0].quantity == 1


def test_postgres_parallel_http_adds_are_atomic(isolated_shop, monkeypatch):
    shop = isolated_shop
    if shop.engine.dialect.name != "postgresql":
        pytest.skip("Requires real PostgreSQL; set DATABASE_URL to a test database")
    monkeypatch.setattr(main, "shop", shop)
    item = shop.create_item(ItemInput(name="Milk", price=2.5))
    cart_id = shop.create_cart()
    barrier = Barrier(8)

    def add_items(worker):
        barrier.wait(timeout=10)
        for _ in range(6):
            response = client.post(f"/cart/{cart_id}/add/{item.id}")
            assert response.status_code == 200

    with TestClient(main.app) as client, ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(add_items, range(8)))
    cart = shop.get_cart(cart_id)
    assert cart.items[0].quantity == 48
    assert cart.price == 120
    with shop.sessions() as session:
        assert len(list(session.scalars(select(CartPosition)))) == 1


def test_overflowing_add_rolls_back_quantity(isolated_shop, monkeypatch):
    monkeypatch.setattr(main, "shop", isolated_shop)
    with TestClient(main.app) as client:
        item = client.post("/item", json={"name": "Large", "price": 1e308}).json()
        cart_id = client.post("/cart").json()["id"]
        first = client.post(f"/cart/{cart_id}/add/{item['id']}")
        assert first.status_code == 200
        assert first.json()["price"] == 1e308
        assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 422
        assert client.get(f"/cart/{cart_id}").json() == first.json()
        filtered = client.get("/cart", params={"max_price": 100})
        assert filtered.status_code == 200
        assert filtered.json() == []


@pytest.mark.parametrize("method", ["put", "patch"])
def test_overflowing_price_change_rolls_back_item(isolated_shop, monkeypatch, method):
    monkeypatch.setattr(main, "shop", isolated_shop)
    with TestClient(main.app) as client:
        item = client.post("/item", json={"name": "Milk", "price": 1}).json()
        cart_id = client.post("/cart").json()["id"]
        for _ in range(2):
            client.post(f"/cart/{cart_id}/add/{item['id']}")
        cart = client.get(f"/cart/{cart_id}").json()
        response = getattr(client, method)(
            f"/item/{item['id']}", json={"name": "Large", "price": 1e308}
        )
        assert response.status_code == 422
        assert client.get(f"/item/{item['id']}").json() == item
        assert client.get(f"/cart/{cart_id}").json() == cart
        assert client.get("/cart", params={"min_price": 2, "max_price": 2}).json() == [
            cart
        ]


def test_overflowing_replacement_does_not_restore_deleted_item(
    isolated_shop, monkeypatch
):
    monkeypatch.setattr(main, "shop", isolated_shop)
    with TestClient(main.app) as client:
        item = client.post("/item", json={"name": "Milk", "price": 1}).json()
        cart_id = client.post("/cart").json()["id"]
        for _ in range(2):
            client.post(f"/cart/{cart_id}/add/{item['id']}")
        client.delete(f"/item/{item['id']}")
        cart = client.get(f"/cart/{cart_id}").json()
        response = client.put(
            f"/item/{item['id']}", json={"name": "Large", "price": 1e308}
        )
        assert response.status_code == 422
        assert isolated_shop.get_item(
            item["id"], include_deleted=True
        ).model_dump() == dict(item, deleted=True)
        assert client.get(f"/cart/{cart_id}").json() == cart


def test_postgres_shared_cart_serializes_different_item_price_changes(
    isolated_shop, monkeypatch
):
    shop = isolated_shop
    if shop.engine.dialect.name != "postgresql":
        pytest.skip("Requires real PostgreSQL; set DATABASE_URL to a test database")
    monkeypatch.setattr(main, "shop", shop)
    items = [
        shop.create_item(ItemInput(name=name, price=1)) for name in ("Milk", "Bread")
    ]
    cart_id = shop.create_cart()
    for item in items:
        shop.add_item(cart_id, item.id)
    barrier = Barrier(2)

    def patch_price(item):
        barrier.wait(timeout=10)
        return client.patch(f"/item/{item.id}", json={"price": 1e308})

    with TestClient(main.app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        with shop.sessions.begin() as blocker:
            blocker.execute(
                select(CartRow).where(CartRow.id == cart_id).with_for_update()
            )
            futures = [pool.submit(patch_price, item) for item in items]
            try:
                deadline = monotonic() + 10
                while True:
                    blocker.execute(text("SELECT pg_stat_clear_snapshot()"))
                    waiting = blocker.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE datname = current_database() AND wait_event_type = 'Lock' "
                            "AND query LIKE '%carts%FOR UPDATE%'"
                        )
                    )
                    if waiting == 2:
                        break
                    assert not all(future.done() for future in futures), (
                        "Price changes bypassed cart locking"
                    )
                    assert monotonic() < deadline, (
                        "Price changes did not wait for the shared cart lock"
                    )
                    sleep(0.02)
            finally:
                blocker.rollback()
        responses = [future.result(timeout=10) for future in futures]
        assert sorted(response.status_code for response in responses) == [200, 422]
        assert sorted(shop.get_item(item.id).price for item in items) == [1, 1e308]
        cart = client.get(f"/cart/{cart_id}")
        assert cart.status_code == 200
        assert cart.json()["price"] == 1e308
        listing = client.get("/cart", params={"max_price": 1e308})
        assert listing.status_code == 200
        assert listing.json() == [cart.json()]
