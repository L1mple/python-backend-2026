from contextlib import asynccontextmanager
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import asyncio
import pytest
from faker import Faker
from fastapi.testclient import TestClient
from websockets.exceptions import ConnectionClosed

from shop_api import chat_client
from shop_api.chat.manager import ChatManager
from shop_api.main import app

client = TestClient(app)
faker = Faker()


@pytest.fixture()
def item() -> dict:
    return client.post(
        "/item",
        json={"name": f"Товар {uuid4().hex}", "price": 42.0},
    ).json()


@pytest.fixture()
def cart_id() -> int:
    return client.post("/cart").json()["id"]


# ########## Item ##########

def test_create_item() -> None:
    response = client.post("/item", json={"name": "Тестовый товар", "price": 9.99})

    assert response.status_code == HTTPStatus.CREATED
    assert response.headers["Location"].startswith("/item/")
    assert response.json()["name"] == "Тестовый товар"


def test_get_item(item: dict) -> None:
    response = client.get(f"/item/{item['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == item


# ########## Item: 404 и 304 ##########

def test_get_deleted_item_returns_404(item: dict) -> None:
    client.delete(f"/item/{item['id']}")

    response = client.get(f"/item/{item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_nonexistent_item_returns_404() -> None:
    response = client.get("/item/999999")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_item_updates_existing(item: dict) -> None:
    response = client.put(
        f"/item/{item['id']}",
        json={"name": "Новое имя", "price": 100.0},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "Новое имя"


def test_put_nonexistent_item_returns_304() -> None:
    response = client.put(
        "/item/999999",
        json={"name": "Нет такого", "price": 100.0},
    )

    assert response.status_code == HTTPStatus.NOT_MODIFIED


def test_patch_item_updates_existing(item: dict) -> None:
    response = client.patch(f"/item/{item['id']}", json={"price": 55.5})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["price"] == pytest.approx(55.5)


def test_patch_item_without_changes(item: dict) -> None:
    response = client.patch(f"/item/{item['id']}", json={})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == item


def test_patch_deleted_item_returns_304(item: dict) -> None:
    client.delete(f"/item/{item['id']}")

    response = client.patch(f"/item/{item['id']}", json={"price": 1.0})
    assert response.status_code == HTTPStatus.NOT_MODIFIED


def test_delete_item(item: dict) -> None:
    assert client.delete(f"/item/{item['id']}").status_code == HTTPStatus.OK
    assert client.get(f"/item/{item['id']}").status_code == HTTPStatus.NOT_FOUND


# ########## Item: фильтры и нумерация ##########

def test_get_items_with_price_filters() -> None:
    cheap = client.post("/item", json={"name": "cheap", "price": 1.0}).json()
    pricey = client.post("/item", json={"name": "pricey", "price": 1000.0}).json()

    response = client.get(
        "/item",
        params={"min_price": 900.0, "max_price": 1100.0, "limit": 1000},
    )

    assert response.status_code == HTTPStatus.OK
    ids = {entry["id"] for entry in response.json()}
    assert pricey["id"] in ids
    assert cheap["id"] not in ids


def test_get_items_with_show_deleted() -> None:
    price = 900_000.0 + faker.pyfloat(min_value=0.0, max_value=1000.0)
    item = client.post(
        "/item",
        json={"name": uuid4().hex, "price": price},
    ).json()
    client.delete(f"/item/{item['id']}")

    response = client.get(
        "/item",
        params={"show_deleted": True, "min_price": price, "max_price": price},
    )

    assert response.status_code == HTTPStatus.OK
    assert item["id"] in [entry["id"] for entry in response.json()]


def test_get_items_pagination() -> None:
    for _ in range(3):
        client.post("/item", json={"name": uuid4().hex, "price": 5.0})

    response = client.get("/item", params={"offset": 1, "limit": 1})

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 1


def test_get_items_validation() -> None:
    queries = (
        {"offset": -1},
        {"limit": 0},
        {"min_price": -1.0},
        {"max_price": -1.0},
    )

    for query in queries:
        assert client.get("/item", params=query).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ########## Cart ##########

def test_create_cart() -> None:
    response = client.post("/cart")

    assert response.status_code == HTTPStatus.CREATED
    assert response.headers["Location"].startswith("/cart/")
    assert response.json()["items"] == []


def test_get_cart(cart_id: int) -> None:
    response = client.get(f"/cart/{cart_id}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["items"] == []


def test_get_nonexistent_cart_returns_404() -> None:
    response = client.get("/cart/999999")

    assert response.status_code == HTTPStatus.NOT_FOUND


# ########## Cart: добавление товаров ##########

def test_add_item_to_cart(cart_id: int, item: dict) -> None:
    response = client.post(
        f"/cart/{cart_id}/add/{item['id']}",
        params={"quantity": 2},
    )

    assert response.status_code == HTTPStatus.OK
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["id"] == item["id"]
    assert cart["items"][0]["quantity"] == 2


def test_add_same_item_twice_increments_quantity(cart_id: int, item: dict) -> None:
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    cart = client.get(f"/cart/{cart_id}").json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 2


def test_add_nonexistent_item_to_cart_returns_404(cart_id: int) -> None:
    response = client.post(f"/cart/{cart_id}/add/999999")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_nonexistent_cart_returns_404(item: dict) -> None:
    response = client.post(f"/cart/999999/add/{item['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_cart_available_false_for_deleted_item(cart_id: int, item: dict) -> None:
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    client.delete(f"/item/{item['id']}")

    response = client.get(f"/cart/{cart_id}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["items"][0]["available"] is False


# ########## Cart: фильтры ##########

def test_get_carts_filter_by_quantity(cart_id: int, item: dict) -> None:
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    response = client.get(
        "/cart",
        params={"min_quantity": 1, "max_quantity": 1000, "limit": 1000},
    )

    assert response.status_code == HTTPStatus.OK
    carts = {entry["id"]: entry for entry in response.json()}
    assert carts[cart_id]["items"][0]["id"] == item["id"]


def test_get_carts_filter_by_price(cart_id: int, item: dict) -> None:
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    response = client.get(
        "/cart",
        params={"min_price": 0.0, "max_price": 1_000_000.0, "limit": 1000},
    )

    assert response.status_code == HTTPStatus.OK


def test_get_carts_validation() -> None:
    queries = (
        {"offset": -1},
        {"limit": 0},
        {"min_quantity": -1},
        {"max_quantity": -1},
    )

    for query in queries:
        assert client.get("/cart", params=query).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ########## WebSocket ##########

def test_websocket_chat_broadcast() -> None:
    with client.websocket_connect("/chat/room") as first:
        with client.websocket_connect("/chat/room") as second:
            first.send_text("hello")
            assert second.receive_text().endswith(" :: hello")


# ########## Chat manager ##########

@pytest.mark.asyncio
async def test_chat_manager_edge_cases() -> None:
    manager = ChatManager()
    manager.disconnect("unknown", object())
    await manager.broadcast("unknown", "text", object())

    sender = MagicMock()
    sender.accept = AsyncMock()
    sender.send_text = AsyncMock()
    dead = MagicMock()
    dead.accept = AsyncMock()
    dead.send_text = AsyncMock(side_effect=RuntimeError)

    await manager.connect("room", sender)
    await manager.connect("room", dead)
    await manager.broadcast("room", "text", sender)

    assert dead not in manager._rooms.get("room", set())


# ########## Chat client ##########

@pytest.mark.asyncio
async def test_recv_loop_prints_messages(capsys) -> None:
    socket = MagicMock()
    socket.recv = AsyncMock(side_effect=["hello", ConnectionClosed(None, None)])

    await chat_client.recv_loop(socket)

    captured = capsys.readouterr()
    assert "hello" in captured.out
    assert "Connection closed" in captured.err


@pytest.mark.asyncio
async def test_send_loop_skips_empty_input(monkeypatch) -> None:
    socket = MagicMock()
    socket.send = AsyncMock()
    answers = iter(["", "   ", "hello", "bye"])

    def fake_input(*args, **kwargs):
        try:
            return next(answers)
        except StopIteration:
            raise RuntimeError("no more input")

    monkeypatch.setattr("builtins.input", fake_input)

    with pytest.raises(RuntimeError):
        await chat_client.send_loop(socket)

    assert [call.args[0] for call in socket.send.await_args_list] == ["hello", "bye"]


def test_main_rejects_empty_room(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "")

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(chat_client.main())

    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_main_connects_to_room(monkeypatch) -> None:
    socket = MagicMock()

    @asynccontextmanager
    async def fake_connect(_):
        yield socket

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "room")
    monkeypatch.setattr(chat_client, "connect", fake_connect)
    monkeypatch.setattr(chat_client, "recv_loop", AsyncMock())
    monkeypatch.setattr(chat_client, "send_loop", AsyncMock())

    await chat_client.main()

    chat_client.recv_loop.assert_awaited_once_with(socket)
    chat_client.send_loop.assert_awaited_once_with(socket)
