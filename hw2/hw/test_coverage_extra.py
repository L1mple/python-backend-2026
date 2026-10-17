"""
hw5: дополнительные тесты, закрывающие пробелы в покрытии test_homework2.py -
в основном 404-ветки (товар/корзина не существуют вовсе, а не просто
удалены) и WebSocket-чат, который в исходном наборе тестов вообще не
затронут.

Отдельный файл, а не правки в test_homework2.py, чтобы не трогать
оригинальный набор тестов задания.
"""
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from faker import Faker
from fastapi.testclient import TestClient

from shop_api.main import app

client = TestClient(app)
faker = Faker()

# Заведомо несуществующий id - тесты ниже ничего с такими id не создают.
_MISSING_ID = 10_000_000


@pytest.fixture()
def existing_item_id() -> int:
    response = client.post(
        "/item",
        json={"name": f"Coverage item {uuid4().hex}", "price": 9.99},
    )
    return response.json()["id"]


@pytest.fixture()
def existing_cart_id() -> int:
    return client.post("/cart").json()["id"]


# --------------------------------------------------------------------------
# 404-ветки: товара/корзины не существует вовсе (не просто deleted)
# --------------------------------------------------------------------------


def test_get_item_not_found() -> None:
    response = client.get(f"/item/{_MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_item_not_found() -> None:
    response = client.put(
        f"/item/{_MISSING_ID}",
        json={"name": "x", "price": 1.0},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_item_not_found() -> None:
    response = client.patch(f"/item/{_MISSING_ID}", json={})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_item_not_found() -> None:
    response = client.delete(f"/item/{_MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_cart_not_found() -> None:
    response = client.get(f"/cart/{_MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_cart_cart_not_found(existing_item_id: int) -> None:
    response = client.post(f"/cart/{_MISSING_ID}/add/{existing_item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_cart_item_not_found(existing_cart_id: int) -> None:
    response = client.post(f"/cart/{existing_cart_id}/add/{_MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


# --------------------------------------------------------------------------
# WebSocket чат (доп. задание из hw2, не покрыт test_homework2.py)
# --------------------------------------------------------------------------


def test_chat_broadcasts_to_other_participants_only() -> None:
    room = f"room-{uuid4().hex}"

    with client.websocket_connect(f"/chat/{room}") as ws1:
        with client.websocket_connect(f"/chat/{room}") as ws2:
            ws1.send_text("hello from 1")
            received_by_2 = ws2.receive_text()
            assert received_by_2.endswith(":: hello from 1")
            assert " :: " in received_by_2

            ws2.send_text("hello from 2")
            received_by_1 = ws1.receive_text()
            assert received_by_1.endswith(":: hello from 2")

            # отправитель не получает собственное сообщение обратно
            ws1.send_text("only for 2")
            received_by_2_again = ws2.receive_text()
            assert received_by_2_again.endswith(":: only for 2")


def test_chat_rooms_are_isolated() -> None:
    room_a = f"room-{uuid4().hex}"
    room_b = f"room-{uuid4().hex}"

    with client.websocket_connect(f"/chat/{room_a}") as ws_a1:
        with client.websocket_connect(f"/chat/{room_a}") as ws_a2:
            with client.websocket_connect(f"/chat/{room_b}") as ws_b1:
                with client.websocket_connect(f"/chat/{room_b}") as ws_b2:
                    # Каждая комната получает только своё сообщение -
                    # если бы комнаты не были изолированы, участник b2
                    # получил бы текст из комнаты a (или вообще ничего
                    # не получил бы, и тест завис/упал по таймауту).
                    ws_a1.send_text("message for room a")
                    received_in_a = ws_a2.receive_text()
                    assert received_in_a.endswith(":: message for room a")

                    ws_b1.send_text("message for room b")
                    received_in_b = ws_b2.receive_text()
                    assert received_in_b.endswith(":: message for room b")


def test_chat_room_cleanup_after_disconnect() -> None:
    room = f"room-{uuid4().hex}"

    with client.websocket_connect(f"/chat/{room}") as ws1:
        ws1.send_text("ping")

    # После выхода всех из комнаты она должна быть удалена из
    # _chat_rooms (строка "if not room: _chat_rooms.pop(...)") - новое
    # подключение к той же комнате должно отработать как в первый раз,
    # без ошибок и без "призрачных" участников.
    with client.websocket_connect(f"/chat/{room}") as ws2:
        with client.websocket_connect(f"/chat/{room}") as ws3:
            ws2.send_text("fresh room")
            received = ws3.receive_text()
            assert received.endswith(":: fresh room")
