from uuid import uuid4

from fastapi.testclient import TestClient
from shop_api.main import chat_rooms


def test_chat_isolates_rooms_does_not_echo_and_cleans_up(client: TestClient) -> None:
    first_room = f"first-{uuid4().hex}"
    second_room = f"second-{uuid4().hex}"
    with client.websocket_connect(f"/chat/{first_room}") as alice:
        with (
            client.websocket_connect(f"/chat/{first_room}") as bob,
            client.websocket_connect(f"/chat/{second_room}") as carol,
            client.websocket_connect(f"/chat/{second_room}") as dave,
        ):
            assert len(chat_rooms[first_room]) == len(chat_rooms[second_room]) == 2
            carol.send_text("second room")
            assert dave.receive_text().partition(" :: ")[2] == "second room"
            alice.send_text("first room")
            message = bob.receive_text()
            username, separator, body = message.partition(" :: ")
            assert username and separator and body == "first room"
            alice.send_text("same sender")
            assert bob.receive_text() == f"{username} :: same sender"
            bob.send_text("reply")
            assert alice.receive_text().partition(" :: ")[2] == "reply"
            carol.send_text("still isolated")
            assert dave.receive_text().partition(" :: ")[2] == "still isolated"
        assert len(chat_rooms[first_room]) == 1
        assert second_room not in chat_rooms
    assert first_room not in chat_rooms
