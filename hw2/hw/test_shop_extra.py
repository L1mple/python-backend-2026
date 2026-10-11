from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from shop_api import main


@pytest.fixture
def client(monkeypatch, isolated_shop):
    monkeypatch.setattr(main, "shop", isolated_shop)
    monkeypatch.setattr(main, "chat", main.Chat())
    with TestClient(main.app) as client:
        yield client


def test_cart_tracks_quantity_updates_and_deleted_items(client):
    item = client.post("/item", json={"name": "Milk", "price": 2.5}).json()
    cart_id = client.post("/cart").json()["id"]
    for _ in range(2):
        assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 200
    assert client.get(f"/cart/{cart_id}").json()["price"] == 5
    client.patch(f"/item/{item['id']}", json={"name": "Fresh milk", "price": 3})
    assert client.get(f"/cart/{cart_id}").json()["price"] == 6
    client.delete(f"/item/{item['id']}")
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"] == [
        {"id": item["id"], "name": "Fresh milk", "quantity": 2, "available": False}
    ]
    assert cart["price"] == 0
    assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 404
    assert client.get(
        "/cart", params={"min_quantity": 2, "max_quantity": 2}
    ).json() == [cart]


def test_filter_before_pagination_and_inclusive_bounds(client):
    for price in (1, 2, 3, 4):
        client.post("/item", json={"name": str(price), "price": price})
    items = client.get(
        "/item", params={"min_price": 2, "max_price": 4, "offset": 1, "limit": 1}
    ).json()
    assert [item["price"] for item in items] == [3]
    carts = [client.post("/cart").json()["id"] for _ in range(3)]
    client.post(f"/cart/{carts[1]}/add/2")
    client.post(f"/cart/{carts[2]}/add/3")
    result = client.get(
        "/cart",
        params={
            "min_price": 2,
            "max_price": 3,
            "min_quantity": 1,
            "max_quantity": 1,
            "offset": 1,
            "limit": 1,
        },
    ).json()
    assert [cart["id"] for cart in result] == [carts[2]]


@pytest.mark.parametrize("path", ["/item/999", "/cart/999"])
def test_missing_resources(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_missing_item_mutations(client, method):
    assert (
        getattr(client, method)(
            "/item/999",
            **({"json": {"name": "Milk", "price": 1}} if method != "delete" else {}),
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "body",
    [
        {"name": "Milk", "price": -1},
        {"name": "Milk", "price": "nan"},
        {"name": "Milk", "price": "inf"},
    ],
)
def test_invalid_item_prices(client, body):
    assert client.post("/item", json=body).status_code == 422


def test_server_assigns_ids_and_patch_rejects_id_and_null(client):
    first = client.post("/item", json={"id": 999, "name": "Milk", "price": 1}).json()
    second = client.post("/item", json={"id": 999, "name": "Bread", "price": 2}).json()
    assert first["id"] != second["id"]
    assert first["id"] != 999
    for patch in ({"id": 999}, {"name": None}, {"price": None}):
        assert client.patch(f"/item/{first['id']}", json=patch).status_code == 422
    replacement = client.put(
        f"/item/{first['id']}", json={"id": 999, "name": "Cheese", "price": 3}
    ).json()
    assert replacement["id"] == first["id"]


def test_deleted_item_visibility_and_replacement(client):
    item = client.post("/item", json={"name": "Milk", "price": 1}).json()
    client.delete(f"/item/{item['id']}")
    assert client.get("/item").json() == []
    assert client.get("/item", params={"show_deleted": True}).json() == [
        dict(item, deleted=True)
    ]
    assert client.patch(f"/item/{item['id']}", json={"price": 2}).status_code == 304
    assert (
        client.put(f"/item/{item['id']}", json={"name": "Milk", "price": 2}).status_code
        == 200
    )
    assert client.get(f"/item/{item['id']}").json()["deleted"] is False


def test_websocket_room_isolation_sender_exclusion_and_cleanup(client):
    room_a, room_b = uuid4().hex, uuid4().hex
    with (
        client.websocket_connect(f"/chat/{room_a}") as a1,
        client.websocket_connect(f"/chat/{room_a}") as a2,
        client.websocket_connect(f"/chat/{room_b}") as b1,
        client.websocket_connect(f"/chat/{room_b}") as b2,
    ):
        a1.send_text("hello A")
        username, message = a2.receive_text().split(" :: ", 1)
        assert username
        assert message == "hello A"
        b1.send_text("hello B")
        assert b2.receive_text().split(" :: ", 1)[1] == "hello B"
        a2.send_text("reply A")
        assert a1.receive_text().split(" :: ", 1)[1] == "reply A"
    assert main.chat.rooms == {}


def test_add_missing_cart_and_item_leaves_cart_unchanged(client):
    item = client.post("/item", json={"name": "Milk", "price": 1}).json()
    assert client.post(f"/cart/999/add/{item['id']}").status_code == 404
    cart_id = client.post("/cart").json()["id"]
    assert client.post(f"/cart/{cart_id}/add/999").status_code == 404
    assert client.get(f"/cart/{cart_id}").json()["items"] == []


@pytest.mark.asyncio
async def test_failed_recipient_does_not_interrupt_room_broadcast():
    class Connection:
        """WebSocket transport with optional send failure."""

        def __init__(self, fails=False):
            self.fails = fails
            self.messages = []

        async def accept(self):
            pass

        async def send_text(self, message):
            if self.fails:
                raise OSError("Connection closed")
            self.messages.append(message)

    chat = main.Chat()
    sender, broken, healthy = Connection(), Connection(True), Connection()
    for connection in (sender, broken, healthy):
        await chat.connect("room", connection)
    await chat.broadcast("room", sender, "hello")
    assert sender.messages == []
    assert healthy.messages[0].endswith(" :: hello")
    assert broken not in chat.rooms["room"]


@pytest.mark.parametrize("same_item", [True, False])
def test_overflowing_add_preserves_cart(client, same_item):
    first = client.post("/item", json={"name": "Large", "price": 1e308}).json()
    second = (
        first
        if same_item
        else client.post("/item", json={"name": "Other", "price": 1e308}).json()
    )
    cart_id = client.post("/cart").json()["id"]
    client.post(f"/cart/{cart_id}/add/{first['id']}")
    before = client.get(f"/cart/{cart_id}").json()
    assert client.post(f"/cart/{cart_id}/add/{second['id']}").status_code == 422
    assert client.get(f"/cart/{cart_id}").json() == before
    assert client.get("/cart", params={"max_price": 1e308}).json() == [before]


@pytest.mark.parametrize("method", ["put", "patch"])
def test_overflowing_price_change_preserves_item_and_all_carts(client, method):
    item = client.post("/item", json={"name": "Original", "price": 1e307}).json()
    cart_ids = [client.post("/cart").json()["id"] for _ in range(2)]
    for quantity, cart_id in enumerate(cart_ids, 1):
        for _ in range(quantity):
            client.post(f"/cart/{cart_id}/add/{item['id']}")
    carts = client.get("/cart").json()
    response = getattr(client, method)(
        f"/item/{item['id']}", json={"name": "Changed", "price": 1e308}
    )
    assert response.status_code == 422
    assert client.get(f"/item/{item['id']}").json() == item
    assert client.get("/cart", params={"max_price": 1e308}).json() == carts


def test_cart_read_rejects_nonfinite_stored_total(client):
    item = client.post("/item", json={"name": "Large", "price": 1e308}).json()
    cart_id = client.post("/cart").json()["id"]
    main.shop.carts[cart_id][item["id"]] = 2
    assert client.get(f"/cart/{cart_id}").status_code == 422
    assert client.get("/cart", params={"max_price": 100}).status_code == 422
