from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import WebSocket, WebSocketDisconnect
from shop_api import chat
from shop_api.chat import ChatRooms


@pytest.mark.asyncio
async def test_connect_and_disconnect():
    rooms = ChatRooms()
    first = AsyncMock(spec=WebSocket)
    second = AsyncMock(spec=WebSocket)

    await rooms.connect("room", first)
    await rooms.connect("room", second)

    first.accept.assert_awaited_once_with()
    second.accept.assert_awaited_once_with()
    assert rooms.rooms == {"room": {first, second}}

    rooms.disconnect("room", first)
    assert rooms.rooms == {"room": {second}}
    rooms.disconnect("room", first)
    assert rooms.rooms == {"room": {second}}
    rooms.disconnect("room", second)
    assert rooms.rooms == {}
    rooms.disconnect("missing", first)
    assert rooms.rooms == {}


@pytest.mark.asyncio
async def test_broadcast_only_reaches_other_members_of_the_same_room():
    rooms = ChatRooms()
    sender, receiver, stranger = [AsyncMock(spec=WebSocket) for _ in range(3)]
    await rooms.connect("room", sender)
    await rooms.connect("room", receiver)
    await rooms.connect("other", stranger)

    await rooms.broadcast("room", sender, "hello")

    receiver.send_text.assert_awaited_once_with("hello")
    sender.send_text.assert_not_awaited()
    stranger.send_text.assert_not_awaited()
    await rooms.broadcast("missing", sender, "ignored")
    assert "missing" not in rooms.rooms
    assert receiver.send_text.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [WebSocketDisconnect, OSError, RuntimeError])
async def test_broadcast_removes_failed_connections_and_keeps_delivering(error):
    rooms = ChatRooms()
    sender, failed, receiver = [AsyncMock(spec=WebSocket) for _ in range(3)]
    await rooms.connect("room", sender)
    await rooms.connect("room", failed)
    await rooms.connect("room", receiver)
    failed.send_text.side_effect = error()

    await rooms.broadcast("room", sender, "hello")

    failed.send_text.assert_awaited_once_with("hello")
    receiver.send_text.assert_awaited_once_with("hello")
    assert rooms.rooms == {"room": {sender, receiver}}
    await rooms.broadcast("room", sender, "again")
    assert failed.send_text.await_count == 1
    receiver.send_text.assert_awaited_with("again")


@pytest.mark.timeout(30)
def test_chat_messages_names_and_room_isolation(isolated_api, monkeypatch):
    rooms = ChatRooms()
    monkeypatch.setattr(chat, "chat_rooms", rooms)

    with (
        isolated_api.websocket_connect("/chat/first") as first,
        isolated_api.websocket_connect("/chat/first") as second,
        isolated_api.websocket_connect("/chat/other") as third,
        isolated_api.websocket_connect("/chat/other") as fourth,
    ):
        first.send_text("Привет :: всем")
        first_name, message = second.receive_text().split(" :: ", 1)
        assert UUID(hex=first_name).hex == first_name
        assert message == "Привет :: всем"

        second.send_text("reply")
        second_name, message = first.receive_text().split(" :: ", 1)
        assert UUID(hex=second_name).hex == second_name
        assert second_name != first_name
        assert message == "reply"

        first.send_text("")
        assert second.receive_text() == f"{first_name} :: "

        third.send_text("separate room")
        third_name, message = fourth.receive_text().split(" :: ", 1)
        assert UUID(hex=third_name).hex == third_name
        assert message == "separate room"

        fourth.send_text("other reply")
        assert third.receive_text().endswith(" :: other reply")

    assert rooms.rooms == {}
