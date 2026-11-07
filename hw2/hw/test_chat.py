import re

from fastapi.testclient import TestClient

from shop_api.main import app


def test_chat_broadcasts_within_room() -> None:
    with TestClient(app) as client:
        with (
            client.websocket_connect("/chat/room-a") as alice,
            client.websocket_connect("/chat/room-a") as bob,
            client.websocket_connect("/chat/room-b") as carol,
        ):
            carol.send_text("only for room b")
            alice.send_text("hello")

            # Боб получает сообщение Алисы, а не Кэрол из другого чата
            assert re.fullmatch(r"\S+ :: hello", bob.receive_text())

            bob.send_text("hi")
            assert re.fullmatch(r"\S+ :: hi", alice.receive_text())


def test_chat_usernames_differ() -> None:
    with TestClient(app) as client:
        with (
            client.websocket_connect("/chat/names") as first,
            client.websocket_connect("/chat/names") as second,
        ):
            first.send_text("ping")
            second.send_text("pong")

            name_first = second.receive_text().split(" :: ")[0]
            name_second = first.receive_text().split(" :: ")[0]
            assert name_first != name_second
