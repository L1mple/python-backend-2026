import asyncio
import re
from uuid import uuid4

from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from shop_api.main import app, chat, chat_rooms

client = TestClient(app)
MISSING_ID = 2_000_000_000


def create_item(price: float, name: str | None = None) -> dict:
    response = client.post(
        "/item",
        json={"name": name or f"Coverage item {uuid4().hex}", "price": price},
    )
    assert response.status_code == 201
    return response.json()


def create_cart() -> int:
    response = client.post("/cart")
    assert response.status_code == 201
    return response.json()["id"]


def add_item(cart_id: int, item_id: int, quantity: int = 1) -> None:
    for _ in range(quantity):
        response = client.post(f"/cart/{cart_id}/add/{item_id}")
        assert response.status_code == 200


def test_missing_cart_and_item_routes_return_404() -> None:
    assert client.get(f"/cart/{MISSING_ID}").status_code == 404
    assert client.post(f"/cart/{MISSING_ID}/add/{MISSING_ID}").status_code == 404

    cart_id = create_cart()
    assert client.post(f"/cart/{cart_id}/add/{MISSING_ID}").status_code == 404

    assert client.get(f"/item/{MISSING_ID}").status_code == 404
    assert client.put(
        f"/item/{MISSING_ID}", json={"name": "missing", "price": 1}
    ).status_code == 404
    assert client.patch(f"/item/{MISSING_ID}", json={"name": "missing"}).status_code == 404
    assert client.delete(f"/item/{MISSING_ID}").status_code == 404


def test_item_validation_rejects_invalid_create_and_null_patch_fields() -> None:
    assert client.post(
        "/item", json={"name": "negative", "price": -0.01}
    ).status_code == 422
    assert client.post(
        "/item", json={"name": "extra", "price": 1, "unexpected": True}
    ).status_code == 422

    item_id = create_item(10.0)["id"]
    assert client.patch(f"/item/{item_id}", json={"name": None}).status_code == 422
    assert client.patch(f"/item/{item_id}", json={"price": None}).status_code == 422


def test_deleted_cart_item_stays_unavailable_and_keeps_its_price() -> None:
    item = create_item(6.25)
    cart_id = create_cart()
    add_item(cart_id, item["id"], quantity=2)

    assert client.delete(f"/item/{item['id']}").status_code == 200

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart == {
        "id": cart_id,
        "items": [
            {
                "id": item["id"],
                "name": item["name"],
                "quantity": 2,
                "available": False,
            }
        ],
        "price": 12.5,
    }


def test_cart_list_filters_price_quantity_and_pagination_per_cart() -> None:
    expensive_once = create_item(100_000)
    expensive_three_times = create_item(50_000)
    expensive_four_times = create_item(40_000)

    one_item_cart = create_cart()
    three_item_cart = create_cart()
    four_item_cart = create_cart()
    add_item(one_item_cart, expensive_once["id"])
    add_item(three_item_cart, expensive_three_times["id"], quantity=3)
    add_item(four_item_cart, expensive_four_times["id"], quantity=4)

    def cart_ids(**query: int) -> list[int]:
        query.setdefault("limit", 1_000)
        response = client.get("/cart", params=query)
        assert response.status_code == 200
        return [cart["id"] for cart in response.json()]

    price_filtered = cart_ids(min_price=100_000)
    assert price_filtered == [one_item_cart, three_item_cart, four_item_cart]
    assert one_item_cart in cart_ids(max_price=100_000)
    assert three_item_cart not in cart_ids(max_price=100_000)
    assert four_item_cart not in cart_ids(max_price=100_000)

    assert one_item_cart not in cart_ids(min_quantity=2)
    assert three_item_cart in cart_ids(min_quantity=2)
    assert four_item_cart in cart_ids(min_quantity=2)
    assert one_item_cart in cart_ids(max_quantity=1)
    assert three_item_cart not in cart_ids(max_quantity=1)
    assert four_item_cart not in cart_ids(max_quantity=1)

    assert cart_ids(min_price=100_000, offset=0, limit=2) == [
        one_item_cart,
        three_item_cart,
    ]
    assert cart_ids(min_price=100_000, offset=1, limit=1) == [three_item_cart]


def test_deleted_item_list_and_update_rules() -> None:
    item = create_item(5.0)
    item_id = item["id"]
    assert client.delete(f"/item/{item_id}").status_code == 200

    visible_items = client.get("/item", params={"limit": 1_000}).json()
    deleted_items = client.get(
        "/item", params={"show_deleted": "true", "limit": 1_000}
    ).json()
    assert all(row["id"] != item_id for row in visible_items)
    assert any(row["id"] == item_id for row in deleted_items)

    replacement = client.put(
        f"/item/{item_id}", json={"name": "Replaced after deletion", "price": 7.5}
    )
    assert replacement.status_code == 200
    assert replacement.json() == {
        "id": item_id,
        "name": "Replaced after deletion",
        "price": 7.5,
        "deleted": True,
    }
    assert client.patch(f"/item/{item_id}", json={}).status_code == 304


def test_chat_broadcasts_to_same_room_and_cleans_up_connections() -> None:
    room_name = f"coverage-{uuid4().hex}"
    other_room = f"coverage-{uuid4().hex}"

    with client.websocket_connect(f"/chat/{room_name}") as sender:
        with client.websocket_connect(f"/chat/{room_name}") as receiver:
            with client.websocket_connect(f"/chat/{other_room}"):
                assert len(chat_rooms[room_name]) == 2
                assert len(chat_rooms[other_room]) == 1

                sender.send_text("hello from coverage")
                username, message = receiver.receive_text().split(" :: ", maxsplit=1)

                assert re.fullmatch(r"[0-9a-f]{8}", username)
                assert message == "hello from coverage"

    assert room_name not in chat_rooms
    assert other_room not in chat_rooms


class _RoomBarrier:
    def __init__(self, participant_count: int) -> None:
        self.participant_count = participant_count
        self.arrived = 0
        self.ready = asyncio.Event()

    async def wait(self) -> None:
        self.arrived += 1
        if self.arrived == self.participant_count:
            self.ready.set()
        await self.ready.wait()


class _CoordinatedSocket:
    def __init__(
        self,
        barrier: _RoomBarrier,
        finished: asyncio.Event,
        message: str | None = None,
    ) -> None:
        self.barrier = barrier
        self.finished = finished
        self.message = message
        self.connected = False
        self.sent_messages: list[str] = []

    async def accept(self) -> None:
        pass

    async def receive_text(self) -> str:
        if not self.connected:
            self.connected = True
            await self.barrier.wait()
            if self.message is not None:
                return self.message
            await self.finished.wait()
        else:
            self.finished.set()
        raise WebSocketDisconnect(code=1000)

    async def send_text(self, message: str) -> None:
        self.sent_messages.append(message)


def test_chat_does_not_cross_rooms_or_echo_to_sender() -> None:
    room_name = f"source-{uuid4().hex}"
    other_room = f"destination-{uuid4().hex}"
    barrier = _RoomBarrier(participant_count=3)
    finished = asyncio.Event()
    sender = _CoordinatedSocket(barrier, finished, message="private room message")
    same_room_peer = _CoordinatedSocket(barrier, finished)
    other_room_peer = _CoordinatedSocket(barrier, finished)

    async def run_chat_connections() -> None:
        await asyncio.gather(
            chat(sender, room_name),
            chat(same_room_peer, room_name),
            chat(other_room_peer, other_room),
        )

    asyncio.run(run_chat_connections())

    assert sender.sent_messages == []
    assert other_room_peer.sent_messages == []
    assert len(same_room_peer.sent_messages) == 1
    username, message = same_room_peer.sent_messages[0].split(" :: ", maxsplit=1)
    assert re.fullmatch(r"[0-9a-f]{8}", username)
    assert message == "private room message"
    assert room_name not in chat_rooms
    assert other_room not in chat_rooms


class DisconnectingSocket:
    def __init__(self) -> None:
        self.messages_read = 0

    async def accept(self) -> None:
        pass

    async def receive_text(self) -> str:
        self.messages_read += 1
        if self.messages_read == 1:
            return "trigger stale peer cleanup"
        raise WebSocketDisconnect(code=1000)


class StalePeer:
    async def send_text(self, _message: str) -> None:
        raise RuntimeError("socket is closed")


def test_chat_removes_stale_peers_after_send_failure() -> None:
    room_name = f"stale-{uuid4().hex}"
    chat_rooms[room_name] = {StalePeer(): "deadbeef"}

    asyncio.run(chat(DisconnectingSocket(), room_name))

    assert room_name not in chat_rooms
