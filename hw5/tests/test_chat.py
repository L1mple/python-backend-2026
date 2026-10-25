import asyncio

from fastapi import WebSocketDisconnect
from shop_api.main import ChatRooms, chat, chat_rooms


class FakeWebSocket:
    def __init__(self, messages=None):
        self.messages = iter(messages or [])
        self.accepted = False
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, message):
        self.sent.append(message)

    async def receive_text(self):
        try:
            return next(self.messages)
        except StopIteration as error:
            raise WebSocketDisconnect from error


def test_chat_rooms_connect_broadcast_and_disconnect():
    rooms = ChatRooms()
    sender = FakeWebSocket()
    recipient = FakeWebSocket()

    asyncio.run(rooms.connect("general", sender))
    asyncio.run(rooms.connect("general", recipient))
    assert sender.accepted and recipient.accepted

    asyncio.run(rooms.broadcast("general", sender, "hello"))
    assert sender.sent == []
    assert recipient.sent == ["hello"]

    rooms.disconnect("missing", sender)
    rooms.disconnect("general", sender)
    assert rooms.connections["general"] == {recipient}
    rooms.disconnect("general", recipient)
    assert "general" not in rooms.connections


def test_broadcast_to_missing_room_does_nothing():
    asyncio.run(ChatRooms().broadcast("missing", FakeWebSocket(), "hello"))


def test_chat_broadcasts_message_and_disconnects(monkeypatch):
    websocket = FakeWebSocket(["hello"])
    calls = []

    async def remember_broadcast(chat_name, sender, message):
        calls.append((chat_name, sender, message))

    monkeypatch.setattr(chat_rooms, "broadcast", remember_broadcast)
    asyncio.run(chat(websocket, "general"))

    assert websocket.accepted is True
    assert calls[0][0:2] == ("general", websocket)
    assert calls[0][2].endswith(" :: hello")
    assert len(calls[0][2].split(" :: ")[0]) == 8
    assert chat_rooms.connections == {}
