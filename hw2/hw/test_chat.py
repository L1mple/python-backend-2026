from fastapi.testclient import TestClient

from shop_api.chat import rooms
from shop_api.main import app

client = TestClient(app)


def test_message_goes_to_others_in_room() -> None:
    with client.websocket_connect("/chat/room") as alice, client.websocket_connect("/chat/room") as bob:
        alice.send_text("hello")
        message = bob.receive_text()

    username, text = message.split(" :: ")
    assert username.startswith("user-")
    assert text == "hello"


def test_other_room_does_not_get_message() -> None:
    with (
        client.websocket_connect("/chat/first") as alice,
        client.websocket_connect("/chat/first") as bob,
        client.websocket_connect("/chat/second") as carol,
    ):
        carol.send_text("only for second")
        alice.send_text("for first")

        # bob'a ilk gelen mesaj alice'inki olmali, carol'unki degil
        assert bob.receive_text().endswith(" :: for first")


def test_users_have_different_names() -> None:
    with client.websocket_connect("/chat/names") as alice, client.websocket_connect("/chat/names") as bob:
        alice.send_text("1")
        bob.send_text("2")
        alice_name = bob.receive_text().split(" :: ")[0]
        bob_name = alice.receive_text().split(" :: ")[0]

    assert alice_name != bob_name


def test_room_removed_after_everyone_left() -> None:
    with client.websocket_connect("/chat/empty"):
        assert "empty" in rooms

    assert "empty" not in rooms
