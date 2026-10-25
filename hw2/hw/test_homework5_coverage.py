import re
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from shop_api import main
from shop_api.main import app

client = TestClient(app)

MISSING_ID = 10**9


def create_item(name: str = "Тестовый товар", price: float = 100.0) -> dict:
    response = client.post("/item", json={"name": name, "price": price})
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


def create_cart() -> int:
    response = client.post("/cart")
    assert response.status_code == HTTPStatus.CREATED
    return response.json()["id"]




def test_get_cart_not_found() -> None:
    response = client.get(f"/cart/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_missing_cart() -> None:
    item = create_item()
    response = client.post(f"/cart/{MISSING_ID}/add/{item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item_to_cart() -> None:
    cart_id = create_cart()
    response = client.post(f"/cart/{cart_id}/add/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_same_item_twice_increases_quantity() -> None:
    item = create_item(price=50.5)
    cart_id = create_cart()

    client.post(f"/cart/{cart_id}/add/{item['id']}")
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 2
    assert data["items"][0]["available"] is True
    assert data["price"] == pytest.approx(101.0)


def test_cart_marks_deleted_item_unavailable() -> None:
    item = create_item(price=10.0)
    cart_id = create_cart()
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    client.delete(f"/item/{item['id']}")

    data = client.get(f"/cart/{cart_id}").json()
    assert data["items"][0]["available"] is False
    assert data["price"] == pytest.approx(10.0)


def test_cart_list_filters() -> None:
    item = create_item(price=100.0)
    full_cart = create_cart()
    for _ in range(3):
        client.post(f"/cart/{full_cart}/add/{item['id']}")
    empty_cart = create_cart()

    def ids(**params) -> set[int]:
        response = client.get("/cart", params={"limit": 1000, **params})
        assert response.status_code == HTTPStatus.OK
        return {cart["id"] for cart in response.json()}

    assert {full_cart, empty_cart} <= ids()

    assert full_cart in ids(min_price=300.0)
    assert empty_cart not in ids(min_price=300.0)

    assert full_cart not in ids(max_price=299.99)
    assert empty_cart in ids(max_price=299.99)

    assert full_cart in ids(min_quantity=3)
    assert empty_cart not in ids(min_quantity=3)

    assert full_cart not in ids(max_quantity=2)
    assert empty_cart in ids(max_quantity=2)

    assert ids(offset=10**6) == set()
    assert len(client.get("/cart", params={"limit": 1}).json()) == 1



def test_get_item_not_found() -> None:
    response = client.get(f"/item/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_item_not_found() -> None:
    response = client.put(f"/item/{MISSING_ID}", json={"name": "x", "price": 1.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_item_not_found() -> None:
    response = client.patch(f"/item/{MISSING_ID}", json={"price": 1.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_missing_item_is_idempotent() -> None:
    response = client.delete(f"/item/{MISSING_ID}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


def test_item_list_filters_and_deleted_flag() -> None:
    item = create_item(price=777.5)
    params = {"min_price": 777.5, "max_price": 777.5, "limit": 1000}

    def ids(**extra) -> list[int]:
        response = client.get("/item", params={**params, **extra})
        assert response.status_code == HTTPStatus.OK
        return [i["id"] for i in response.json()]

    assert item["id"] in ids()

    client.delete(f"/item/{item['id']}")

    assert item["id"] not in ids()
    assert item["id"] in ids(show_deleted=True)




def test_random_username_format() -> None:
    assert re.fullmatch(r"user_[a-z0-9]{6}", main.random_username())


@pytest.fixture()
def ws_client():
    with TestClient(app) as test_client:
        yield test_client


def test_chat_broadcasts_to_other_members(ws_client: TestClient) -> None:
    with ws_client.websocket_connect("/chat/room-a") as ws1, \
            ws_client.websocket_connect("/chat/room-a") as ws2:
        ws2.send_text("ready")
        assert ws1.receive_text().endswith(" :: ready")

        ws1.send_text("привет")
        username, separator, text = ws2.receive_text().partition(" :: ")
        assert username.startswith("user_")
        assert separator == " :: "
        assert text == "привет"

        ws2.send_text("pong")
        assert ws1.receive_text().endswith(" :: pong")


def test_chat_rooms_are_isolated(ws_client: TestClient) -> None:
    with ws_client.websocket_connect("/chat/room-b") as other_room, \
            ws_client.websocket_connect("/chat/room-c") as c1, \
            ws_client.websocket_connect("/chat/room-c") as c2:
        c2.send_text("ready")
        assert c1.receive_text().endswith(" :: ready")

        other_room.send_text("secret")
        c2.send_text("hello")

        assert c1.receive_text().endswith(" :: hello")