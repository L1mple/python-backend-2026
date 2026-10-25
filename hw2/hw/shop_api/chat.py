from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ChatRooms:
    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, room_name: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms.setdefault(room_name, set()).add(websocket)

    def disconnect(self, room_name: str, websocket: WebSocket) -> None:
        room = self.rooms.get(room_name)
        if room is not None:
            room.discard(websocket)
            if not room:
                del self.rooms[room_name]

    async def broadcast(self, room_name: str, sender: WebSocket, message: str) -> None:
        for websocket in tuple(self.rooms.get(room_name, ())):
            if websocket is sender:
                continue
            try:
                await websocket.send_text(message)
            except (WebSocketDisconnect, OSError, RuntimeError):
                self.disconnect(room_name, websocket)


chat_rooms = ChatRooms()


@router.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    username = uuid4().hex
    await chat_rooms.connect(chat_name, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await chat_rooms.broadcast(chat_name, websocket, f"{username} :: {message}")
    except WebSocketDisconnect:
        pass
    finally:
        chat_rooms.disconnect(chat_name, websocket)
