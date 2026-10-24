from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect


class Chat:
    """Room membership and message delivery."""

    def __init__(self):
        self.rooms: dict[str, dict[WebSocket, str]] = {}

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(room, {})[websocket] = uuid4().hex

    def disconnect(self, room: str, websocket: WebSocket):
        members = self.rooms.get(room)
        if members is not None:
            members.pop(websocket, None)
            if not members:
                self.rooms.pop(room, None)

    async def broadcast(self, room: str, sender: WebSocket, message: str):
        members = self.rooms.get(room, {})
        username = members.get(sender)
        if username is None:
            return
        for recipient in list(members):
            if recipient is sender:
                continue
            try:
                await recipient.send_text(f"{username} :: {message}")
            except (WebSocketDisconnect, RuntimeError, OSError):
                self.disconnect(room, recipient)
