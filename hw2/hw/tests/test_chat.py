import asyncio
from unittest.mock import AsyncMock

import pytest
from async_asgi_testclient import TestClient
from fastapi import WebSocket, WebSocketDisconnect

from shop_api import main
from shop_api.chat import ChatRooms


async def test_broadcast_reaches_all_peers_with_stable_random_username() -> None:
    async with (
        TestClient(main.app) as client,
        client.websocket_connect("/chat/python") as sender,
        client.websocket_connect("/chat/python") as first,
        client.websocket_connect("/chat/python") as second,
    ):
        await sender.send_text("Привет :: 👋")
        message = await asyncio.wait_for(first.receive_text(), timeout=1)
        assert await asyncio.wait_for(second.receive_text(), timeout=1) == message
        username, text = message.split(" :: ", 1)
        assert username
        assert text == "Привет :: 👋"

        await sender.send_text("")
        assert await asyncio.wait_for(first.receive_text(), timeout=1) == f"{username} :: "
        assert await asyncio.wait_for(second.receive_text(), timeout=1) == f"{username} :: "

        await first.send_text("Ответ")
        reply = await asyncio.wait_for(sender.receive_text(), timeout=1)
        assert reply.split(" :: ", 1)[0] != username
        assert reply.endswith(" :: Ответ")
        assert await asyncio.wait_for(second.receive_text(), timeout=1) == reply


async def test_rooms_are_isolated_and_sender_does_not_receive_own_message() -> None:
    async with (
        TestClient(main.app) as client,
        client.websocket_connect("/chat/python") as sender,
        client.websocket_connect("/chat/python") as peer,
        client.websocket_connect("/chat/other") as outsider,
    ):
        await sender.send_text("Private message")
        assert (await asyncio.wait_for(peer.receive_text(), timeout=1)).endswith(" :: Private message")
        for websocket in (sender, outsider):
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(websocket.receive_text(), timeout=0.05)


async def test_disconnect_removes_empty_room_and_allows_reconnection() -> None:
    async with TestClient(main.app) as client:
        async with client.websocket_connect("/chat/python"):
            assert len(main.chat_rooms.rooms["python"]) == 1
        async with asyncio.timeout(1):
            while main.chat_rooms.rooms:
                await asyncio.sleep(0)

        async with (
            client.websocket_connect("/chat/python") as sender,
            client.websocket_connect("/chat/python") as peer,
        ):
            await sender.send_text("Reconnected")
            assert (await asyncio.wait_for(peer.receive_text(), timeout=1)).endswith(" :: Reconnected")


async def test_binary_message_closes_only_its_connection() -> None:
    async with (
        TestClient(main.app) as client,
        client.websocket_connect("/chat/python") as binary_sender,
        client.websocket_connect("/chat/python") as sender,
        client.websocket_connect("/chat/python") as peer,
    ):
        await binary_sender.send_bytes(b"unsupported")
        message = await asyncio.wait_for(anext(binary_sender), timeout=1)
        assert message["type"] == "websocket.close"
        assert message["code"] == 1003
        await sender.send_text("Still connected")
        assert (await asyncio.wait_for(peer.receive_text(), timeout=1)).endswith(" :: Still connected")


async def test_failed_recipient_does_not_interrupt_broadcast() -> None:
    rooms = ChatRooms()
    sender = AsyncMock(spec=WebSocket)
    failed = AsyncMock(spec=WebSocket)
    peer = AsyncMock(spec=WebSocket)
    failed.send_text.side_effect = WebSocketDisconnect(code=1006)
    rooms.rooms["python"] = {sender, failed, peer}

    await rooms.broadcast("python", sender, "user :: Hello")

    peer.send_text.assert_awaited_once_with("user :: Hello")
    sender.send_text.assert_not_awaited()
    assert rooms.rooms["python"] == {sender, peer}
