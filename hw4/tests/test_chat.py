"""Тесты WebSocket-чата (доп. задание ДЗ2)."""

from fastapi.testclient import TestClient

from shop_api import main


def split(message: str) -> tuple[str, str]:
    username, text = message.split(" :: ", maxsplit=1)
    return username, text


def test_message_reaches_other_users_of_the_same_chat(client: TestClient) -> None:
    with client.websocket_connect("/chat/room-1") as alice, client.websocket_connect("/chat/room-1") as bob:
        alice.send_text("привет")

        username, text = split(bob.receive_text())

    assert text == "привет"
    assert username  # сервер присвоил отправителю имя


def test_sender_does_not_get_own_message_and_names_are_stable(client: TestClient) -> None:
    with client.websocket_connect("/chat/room-2") as alice, client.websocket_connect("/chat/room-2") as bob:
        alice.send_text("раз")
        alice.send_text("два")
        first, second = split(bob.receive_text()), split(bob.receive_text())
        bob.send_text("ответ")
        reply = split(alice.receive_text())  # первое, что получила alice, - это ответ боба

    assert first[0] == second[0]  # у одного клиента одно и то же имя
    assert (first[1], second[1]) == ("раз", "два")
    assert reply[1] == "ответ" and reply[0] != first[0]


def test_other_chats_do_not_receive_messages(client: TestClient) -> None:
    with (
        client.websocket_connect("/chat/room-3") as alice,
        client.websocket_connect("/chat/room-3") as bob,
        client.websocket_connect("/chat/other-room") as stranger,
    ):
        alice.send_text("секрет")
        assert split(bob.receive_text())[1] == "секрет"

        stranger.send_text("из другой комнаты")
        alice.send_text("еще одно")
        # alice получает только сообщения своей комнаты: "из другой комнаты" ей не приходило
        bob.send_text("пинг")
        assert split(alice.receive_text())[1] == "пинг"


def test_empty_room_is_removed_after_everyone_left(client: TestClient) -> None:
    with client.websocket_connect("/chat/room-4"):
        assert "room-4" in main._chat_rooms

    assert "room-4" not in main._chat_rooms
