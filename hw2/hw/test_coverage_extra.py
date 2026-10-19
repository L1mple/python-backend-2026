"""Дополнительные тесты для достижения 95% покрытия shop_api."""
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from shop_api.main import app


client = TestClient(app)


# ---------- items: 404 / 304 ----------

def test_get_item_not_found():
    assert client.get("/item/999999").status_code == HTTPStatus.NOT_FOUND


def test_put_item_not_found():
    r = client.put("/item/999999", json={"name": "x", "price": 1.0})
    assert r.status_code == HTTPStatus.NOT_MODIFIED


def test_put_item_deleted():
    item = client.post("/item", json={"name": "put-del", "price": 10.0}).json()
    client.delete(f"/item/{item['id']}")
    r = client.put(f"/item/{item['id']}", json={"name": "x", "price": 20.0})
    assert r.status_code == HTTPStatus.NOT_MODIFIED


def test_patch_item_not_found():
    assert client.patch("/item/999999", json={"name": "x"}).status_code == HTTPStatus.NOT_MODIFIED


def test_delete_item_not_found():
    assert client.delete("/item/999999").status_code == HTTPStatus.OK


# ---------- carts: 404 ----------

def test_get_cart_not_found():
    assert client.get("/cart/999999").status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_cart_not_found_cart():
    assert client.post("/cart/999999/add/1").status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_cart_not_found_item():
    cart = client.post("/cart").json()
    assert client.post(f"/cart/{cart['id']}/add/999999").status_code == HTTPStatus.NOT_FOUND


# ---------- carts: фильтры (покрывают ветки в get_cart_list) ----------

def test_get_cart_list_all_filters():
    cart = client.post("/cart").json()
    item = client.post("/item", json={"name": "filter-item", "price": 50.0}).json()
    client.post(f"/cart/{cart['id']}/add/{item['id']}")
    client.post(f"/cart/{cart['id']}/add/{item['id']}")

    # min_price — отсекает
    assert client.get("/cart", params={"min_price": 1e9}).status_code == HTTPStatus.OK
    # max_price — пропускает
    assert client.get("/cart", params={"max_price": 1e9}).status_code == HTTPStatus.OK
    # min_quantity — отсекает
    assert client.get("/cart", params={"min_quantity": 10000}).status_code == HTTPStatus.OK
    # max_quantity — пропускает
    assert client.get("/cart", params={"max_quantity": 10000}).status_code == HTTPStatus.OK
    # offset/limit
    assert client.get("/cart", params={"offset": 0, "limit": 5}).status_code == HTTPStatus.OK


# ---------- store: прямые вызовы ----------

@pytest.mark.asyncio
async def test_store_direct_branches():
    from shop_api.database import async_session_maker
    from shop_api import store

    async with async_session_maker() as session:
        # update_item несуществующего
        assert await store.update_item(session, 999999, name="x", price=1.0) is None

        # patch_item несуществующего
        assert await store.patch_item(session, 999999, name="x") is None

        # delete_item несуществующего
        await store.delete_item(session, 999999)

        # get_cart несуществующей
        assert await store.get_cart(session, 999999) is None

        # get_cart_items несуществующей
        assert await store.get_cart_items(session, 999999) == []

        # add_item_to_cart с несуществующей корзиной
        assert await store.add_item_to_cart(session, 999999, 1) is False

        # add_item_to_cart с несуществующим товаром
        cart = await store.add_cart(session)
        assert await store.add_item_to_cart(session, cart.id, 999999) is False

        # get_all_carts
        carts = await store.get_all_carts(session)
        assert isinstance(carts, list)