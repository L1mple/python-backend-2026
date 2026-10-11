from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from shop_api import main
from shop_api.database import CartPosition, ItemRow
from shop_api.models import ItemInput
from shop_api.store import Shop
from sqlalchemy import insert, select
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
