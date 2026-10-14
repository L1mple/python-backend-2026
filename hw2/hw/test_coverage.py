from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from shop_api.main import app
from shop_api.main import chats

client = TestClient(app)


def test_missing_resources_are_not_found() -> None:
    missing = 10**9

    assert client.get(f"/cart/{missing}").status_code == HTTPStatus.NOT_FOUND
    assert client.post(f"/cart/{missing}/add/1").status_code == HTTPStatus.NOT_FOUND

    item = client.post("/item", json={"name": "coverage item", "price": 3.5}).json()
    cart_id = client.post("/cart").json()["id"]
    assert client.post(f"/cart/{cart_id}/add/{missing}").status_code == HTTPStatus.NOT_FOUND

    assert client.put(f"/item/{missing}", json={"name": "x", "price": 1}).status_code == HTTPStatus.NOT_FOUND
    assert client.patch(f"/item/{missing}", json={"price": 1}).status_code == HTTPStatus.NOT_FOUND
    assert client.delete(f"/item/{missing}").status_code == HTTPStatus.NOT_FOUND

    client.post(f"/cart/{cart_id}/add/{item['id']}")
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["quantity"] == 2
    assert cart["price"] == pytest.approx(7.0)


def test_item_list_skips_deleted_and_cheap_items() -> None:
    cheap = client.post("/item", json={"name": "cheap", "price": 1.0}).json()
    deleted = client.post("/item", json={"name": "gone", "price": 20.0}).json()
    client.delete(f"/item/{deleted['id']}")

    listed = client.get("/item", params={"min_price": 10, "limit": 100}).json()
    ids = {item["id"] for item in listed}

    assert cheap["id"] not in ids
    assert deleted["id"] not in ids

    with_deleted = client.get("/item", params={"show_deleted": True, "limit": 100}).json()
    assert deleted["id"] in {item["id"] for item in with_deleted}


def test_chat_broadcasts_inside_one_room() -> None:
    with client.websocket_connect("/chat/kitchen") as first, client.websocket_connect("/chat/kitchen") as second:
        first.send_text("hello")
        received = second.receive_text()

    assert received.endswith(" :: hello")
    assert received.split(" :: ")[0].startswith("user-")
    assert chats.get("kitchen") == []
