"""WebSocket room membership and delivery to the other participants."""

from fastapi import WebSocket, WebSocketDisconnect


class ChatRooms:
    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, chat_name: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms.setdefault(chat_name, set()).add(websocket)

    def disconnect(self, chat_name: str, websocket: WebSocket) -> None:
        participants = self.rooms.get(chat_name)
        if participants is None:
            return
        participants.discard(websocket)
        if not participants:
            del self.rooms[chat_name]

    async def broadcast(self, chat_name: str, sender: WebSocket, message: str) -> None:
        # A participant can disconnect while another participant is sending.
        for websocket in tuple(self.rooms.get(chat_name, ())):
            if websocket is sender:
                continue
            try:
                await websocket.send_text(message)
            except (WebSocketDisconnect, OSError):
                self.disconnect(chat_name, websocket)
