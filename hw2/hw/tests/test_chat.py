from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from shop_api.chat import chat, rooms


def test_broadcast_is_limited_to_room_and_excludes_sender(client):
    assert not rooms
    with client.websocket_connect("/chat/shop") as first:
        with client.websocket_connect("/chat/shop") as second:
            with client.websocket_connect("/chat/other") as other:
                with client.websocket_connect("/chat/other") as other_peer:
                    first.send_text("Hello")
                    message = second.receive_text()
                    username, text = message.split(" :: ", 1)
                    assert username.startswith("user-")
                    assert len(username) == 37
                    assert text == "Hello"

                    second.send_text("Reply")
                    reply = first.receive_text()
                    assert reply.endswith(" :: Reply")
                    assert not reply.startswith(f"{username} :: ")

                    other.send_text("Private")
                    assert other_peer.receive_text().endswith(" :: Private")
                    other_peer.send_text("Private reply")
                    assert other.receive_text().endswith(" :: Private reply")
                    first.send_text("Again")
                    assert second.receive_text() == f"{username} :: Again"
            assert "other" not in rooms
        assert len(rooms["shop"]) == 1
    assert not rooms


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application_state", "client_state", "error"),
    [
        (WebSocketState.DISCONNECTED, WebSocketState.CONNECTED, None),
        (WebSocketState.CONNECTED, WebSocketState.DISCONNECTED, None),
        (WebSocketState.CONNECTED, WebSocketState.CONNECTED, OSError()),
        (WebSocketState.CONNECTED, WebSocketState.CONNECTED, WebSocketDisconnect()),
    ],
)
async def test_disconnected_recipient_is_removed(
    application_state, client_state, error
):
    sender = AsyncMock(spec=WebSocket)
    sender.receive_text.side_effect = ["Hello", WebSocketDisconnect()]
    recipient = AsyncMock(spec=WebSocket)
    recipient.application_state = application_state
    recipient.client_state = client_state
    recipient.send_text.side_effect = error
    rooms["disconnect"] = {recipient}
    try:
        await chat(sender, "disconnect")

        sender.accept.assert_awaited_once()
        sender.send_text.assert_not_awaited()
        if error is None:
            recipient.send_text.assert_not_awaited()
        else:
            recipient.send_text.assert_awaited_once()
        assert "disconnect" not in rooms
    finally:
        rooms.pop("disconnect", None)
