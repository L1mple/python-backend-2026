from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from shop_api.chat import rooms
from shop_api.main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def new_item(client, price=10.0):
    response = client.post("/item", json={"name": uuid4().hex, "price": price})
    assert response.status_code == 201
    assert response.headers["location"] == f"/item/{response.json()['id']}"
    return response.json()


def test_cart_tracks_quantity_price_and_deleted_items(client):
    item = new_item(client)
    cart_id = client.post("/cart").json()["id"]
    for _ in range(2):
        assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 200

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["price"] == 20.0
    assert cart["items"] == [
        {"id": item["id"], "name": item["name"], "quantity": 2, "available": True}
    ]

    client.patch(f"/item/{item['id']}", json={"name": "Updated", "price": 15.0})
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["name"] == "Updated"
    assert cart["price"] == 30.0

    client.delete(f"/item/{item['id']}")
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["price"] == 0.0
    assert cart["items"][0]["available"] is False
    assert cart["items"][0]["quantity"] == 2
    assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 404


def test_item_filters_before_pagination_and_includes_boundaries(client):
    first = new_item(client, 12.0)
    second = new_item(client, 12.0)
    query = {"min_price": 12.0, "max_price": 12.0, "limit": 10000}
    matching = client.get("/item", params=query).json()
    assert {first["id"], second["id"]} <= {item["id"] for item in matching}
    assert all(item["price"] == 12.0 for item in matching)

    index = next(i for i, item in enumerate(matching) if item["id"] == second["id"])
    page = client.get("/item", params={**query, "offset": index, "limit": 1})
    assert page.json() == [second]

    client.delete(f"/item/{first['id']}")
    visible = client.get("/item", params=query).json()
    assert first["id"] not in {item["id"] for item in visible}
    with_deleted = client.get("/item", params={**query, "show_deleted": True}).json()
    assert {**first, "deleted": True} in with_deleted


def test_cart_filters_use_total_quantity_and_price_boundaries(client):
    item = new_item(client, 7.0)
    cart_id = client.post("/cart").json()["id"]
    for _ in range(3):
        client.post(f"/cart/{cart_id}/add/{item['id']}")

    query = {
        "min_price": 21,
        "max_price": 21,
        "min_quantity": 3,
        "max_quantity": 3,
        "limit": 10000,
    }
    matching = client.get("/cart", params=query).json()
    assert cart_id in {cart["id"] for cart in matching}
    assert all(
        cart["price"] == 21
        and sum(item["quantity"] for item in cart["items"]) == 3
        for cart in matching
    )
    index = next(i for i, cart in enumerate(matching) if cart["id"] == cart_id)
    page = client.get("/cart", params={**query, "offset": index, "limit": 1})
    assert page.json() == [client.get(f"/cart/{cart_id}").json()]


def test_patch_preserves_omitted_fields_and_rejects_null(client):
    item = new_item(client)
    path = f"/item/{item['id']}"
    assert client.patch(path, json={}).json() == item
    patched = client.patch(path, json={"name": "Changed"}).json()
    assert patched == {**item, "name": "Changed"}
    invalid_bodies = [
        {"price": None},
        {"name": None},
        {"deleted": False},
        {"id": 999},
        {"price": -1},
    ]
    for body in invalid_bodies:
        assert client.patch(path, json=body).status_code == 422
    assert client.get(path).json() == {**item, "name": "Changed"}
    client.delete(path)
    assert client.patch(path, json={"price": 5}).status_code == 304
    assert client.patch(path, json={"price": 5}).content == b""
    assert client.delete(path).status_code == 200


def test_missing_resources_do_not_create_items_or_change_carts(client):
    item = new_item(client)
    cart_id = client.post("/cart").json()["id"]
    missing = 10**12
    assert client.get(f"/item/{missing}").status_code == 404
    response = client.put(f"/item/{missing}", json={"name": "Missing", "price": 1})
    assert response.status_code == 404
    assert client.get(f"/item/{missing}").status_code == 404
    assert client.get(f"/cart/{missing}").status_code == 404
    assert client.post(f"/cart/{missing}/add/{item['id']}").status_code == 404
    assert client.post(f"/cart/{cart_id}/add/{missing}").status_code == 404
    assert client.get(f"/cart/{cart_id}").json()["items"] == []


@pytest.mark.parametrize("path", ["/item", "/cart"])
def test_invalid_query_parameters(client, path):
    invalid_queries = [
        {"offset": "oops"},
        {"limit": 0},
        {"min_price": "nan"},
        {"max_price": "inf"},
    ]
    for query in invalid_queries:
        assert client.get(path, params=query).status_code == 422


def test_chat_rooms_do_not_leak_messages_or_echo_to_sender(client):
    with (
        client.websocket_connect("/chat/first") as alice,
        client.websocket_connect("/chat/first") as bob,
        client.websocket_connect("/chat/second") as carol,
        client.websocket_connect("/chat/second") as dave,
    ):
        carol.send_text("private")
        carol_name, message = dave.receive_text().split(" :: ", 1)
        assert carol_name and message == "private"

        alice.send_text("hello")
        alice_name, message = bob.receive_text().split(" :: ", 1)
        assert alice_name and message == "hello"
        alice.send_text("again")
        assert bob.receive_text() == f"{alice_name} :: again"

        bob.send_text("reply")
        bob_name, message = alice.receive_text().split(" :: ", 1)
        assert bob_name != alice_name and message == "reply"

        dave.send_text("still private")
        dave_name, message = carol.receive_text().split(" :: ", 1)
        assert dave_name != carol_name and message == "still private"

    assert rooms == {}


def test_chat_continues_after_peer_disconnects(client):
    with client.websocket_connect("/chat/room") as alice:
        with client.websocket_connect("/chat/room") as bob:
            alice.send_text("before")
            username, _ = bob.receive_text().split(" :: ", 1)
        with client.websocket_connect("/chat/room") as charlie:
            alice.send_text("after")
            assert charlie.receive_text() == f"{username} :: after"
    assert rooms == {}
