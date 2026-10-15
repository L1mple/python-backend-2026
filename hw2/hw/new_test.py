import asyncio
from http import HTTPStatus
from uuid import uuid4

import pytest
from faker import Faker
from fastapi.testclient import TestClient

from shop_api.main import app, engine, Base


# Гарантируем, что таблицы созданы (для локального запуска и CI)
async def _create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.run(_create_tables())

client = TestClient(app)
faker = Faker()


# ---------- Хелперы ----------

@pytest.fixture()
def fresh_item() -> dict:
    return client.post(
        "/item",
        json={"name": f"Coverage item {uuid4().hex}", "price": 42.0},
    ).json()


@pytest.fixture()
def fresh_cart_id() -> int:
    return client.post("/cart").json()["id"]


# ---------- Item: 404-ветки ----------

def test_get_deleted_item_returns_404(fresh_item: dict) -> None:
    item_id = fresh_item["id"]
    client.delete(f"/item/{item_id}")
    response = client.get(f"/item/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_nonexistent_item_returns_404() -> None:
    response = client.get("/item/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_item_on_deleted_returns_404(fresh_item: dict) -> None:
    item_id = fresh_item["id"]
    client.delete(f"/item/{item_id}")
    response = client.put(
        f"/item/{item_id}",
        json={"name": "new", "price": 100.0},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_item_on_nonexistent_returns_404() -> None:
    response = client.put(
        "/item/999999",
        json={"name": "new", "price": 100.0},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_nonexistent_item_returns_404() -> None:
    response = client.delete("/item/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_nonexistent_item_returns_404() -> None:
    response = client.patch("/item/999999", json={"price": 1.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


# ---------- Item: фильтры в get_items ----------

def test_get_items_with_both_price_filters() -> None:
    response = client.get("/item", params={"min_price": 10.0, "max_price": 500.0})
    assert response.status_code == HTTPStatus.OK
    for item in response.json():
        assert 10.0 <= item["price"] <= 500.0


def test_get_items_with_show_deleted_true() -> None:
    unique_price = 999_999.0 + faker.pyfloat(min_value=0, max_value=1000)
    item = client.post(
        "/item",
        json={"name": f"Deleted {uuid4().hex}", "price": unique_price},
    ).json()
    item_id = item["id"]
    client.delete(f"/item/{item_id}")

    response = client.get(
        "/item",
        params={
            "show_deleted": True,
            "min_price": unique_price,
            "max_price": unique_price,
        },
    )
    assert response.status_code == HTTPStatus.OK
    ids = [i["id"] for i in response.json()]
    assert item_id in ids


def test_get_items_pagination() -> None:
    # создаём несколько товаров, чтобы была на чём проверять
    for _ in range(3):
        client.post("/item", json={"name": uuid4().hex, "price": 5.0})

    response = client.get("/item", params={"offset": 1, "limit": 1})
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 1


# ---------- Cart: 404-ветки ----------

def test_get_nonexistent_cart_returns_404() -> None:
    response = client.get("/cart/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_nonexistent_cart_returns_404(fresh_item: dict) -> None:
    response = client.post(f"/cart/999999/add/{fresh_item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_nonexistent_item_to_cart_returns_404(fresh_cart_id: int) -> None:
    response = client.post(f"/cart/{fresh_cart_id}/add/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_deleted_item_to_cart_returns_404(fresh_cart_id: int, fresh_item: dict) -> None:
    item_id = fresh_item["id"]
    client.delete(f"/item/{item_id}")
    response = client.post(f"/cart/{fresh_cart_id}/add/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


# ---------- Cart: наполнение, фильтры, повторы ----------

def test_add_same_item_twice_increments_quantity(fresh_cart_id: int, fresh_item: dict) -> None:
    item_id = fresh_item["id"]
    client.post(f"/cart/{fresh_cart_id}/add/{item_id}")
    response = client.post(f"/cart/{fresh_cart_id}/add/{item_id}")
    assert response.status_code == HTTPStatus.OK
    cart = response.json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 2


def test_cart_available_false_for_deleted_item(fresh_cart_id: int, fresh_item: dict) -> None:
    item_id = fresh_item["id"]
    client.post(f"/cart/{fresh_cart_id}/add/{item_id}")
    client.delete(f"/item/{item_id}")

    response = client.get(f"/cart/{fresh_cart_id}")
    assert response.status_code == HTTPStatus.OK
    item = response.json()["items"][0]
    assert item["available"] is False


def test_get_carts_filter_min_quantity(fresh_cart_id: int, fresh_item: dict) -> None:
    client.post(f"/cart/{fresh_cart_id}/add/{fresh_item['id']}")
    response = client.get("/cart", params={"min_quantity": 1})
    assert response.status_code == HTTPStatus.OK
    for cart in response.json():
        total = sum(i["quantity"] for i in cart["items"])
        assert total >= 1


def test_get_carts_filter_max_quantity(fresh_cart_id: int, fresh_item: dict) -> None:
    client.post(f"/cart/{fresh_cart_id}/add/{fresh_item['id']}")
    response = client.get("/cart", params={"max_quantity": 1000})
    assert response.status_code == HTTPStatus.OK


def test_get_carts_filter_min_and_max_price(fresh_cart_id: int, fresh_item: dict) -> None:
    client.post(f"/cart/{fresh_cart_id}/add/{fresh_item['id']}")
    response = client.get("/cart", params={"min_price": 0.0, "max_price": 1_000_000.0})
    assert response.status_code == HTTPStatus.OK


# ---------- WebSocket ----------

def test_websocket_chat_broadcast() -> None:
    with client.websocket_connect("/chat/room1") as ws1:
        with client.websocket_connect("/chat/room1") as ws2:
            ws1.send_text("hello")
            received = ws2.receive_text()
            assert received.endswith(" :: hello")


def test_websocket_chat_isolated_rooms() -> None:
    from shop_api.main import chat_manager

    with client.websocket_connect("/chat/roomA"):
        with client.websocket_connect("/chat/roomB"):
            assert "roomA" in chat_manager.chats
            assert "roomB" in chat_manager.chats
            assert len(chat_manager.chats["roomA"]) == 1
            assert len(chat_manager.chats["roomB"]) == 1


def test_websocket_chat_disconnect_cleans_up() -> None:
    with client.websocket_connect("/chat/room-cleanup"):
        pass  
    from shop_api.main import chat_manager
    assert "room-cleanup" not in chat_manager.chats