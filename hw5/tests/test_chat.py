from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from shop_api.chat import chat, disconnect, rooms


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [WebSocketDisconnect, RuntimeError, OSError])
async def test_failed_subscriber_is_removed_and_others_keep_receiving(error):
    name = uuid4().hex
    sender = AsyncMock(spec=WebSocket)
    sender.receive_text.side_effect = ["first", "second", WebSocketDisconnect()]
    broken = AsyncMock(spec=WebSocket)
    broken.send_text.side_effect = error()
    healthy = AsyncMock(spec=WebSocket)
    rooms[name] = {broken, healthy}
    try:
        await chat(sender, name)
        sender.accept.assert_awaited_once()
        sender.send_text.assert_not_awaited()
        broken.send_text.assert_awaited_once()
        messages = [call.args[0] for call in healthy.send_text.await_args_list]
        assert len(messages) == 2
        username, first = messages[0].split(" :: ", 1)
        assert len(username) == 32
        assert first == "first"
        assert messages[1] == f"{username} :: second"
        assert rooms[name] == {healthy}
        disconnect(name, healthy)
        assert name not in rooms
        # Disconnect can race with broadcast cleanup; repeating it must be safe.
        disconnect(name, healthy)
        assert name not in rooms
    finally:
        rooms.pop(name, None)
