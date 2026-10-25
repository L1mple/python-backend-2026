from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
rooms: dict[str, set[WebSocket]] = {}


def disconnect(chat_name: str, websocket: WebSocket) -> None:
    room = rooms.get(chat_name)
    if room is not None:
        room.discard(websocket)
        if not room:
            del rooms[chat_name]


@router.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()
    username = uuid4().hex
    rooms.setdefault(chat_name, set()).add(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            for subscriber in tuple(rooms.get(chat_name, ())):
                if subscriber is websocket:
                    continue
                try:
                    await subscriber.send_text(f"{username} :: {message}")
                except (WebSocketDisconnect, RuntimeError, OSError):
                    disconnect(chat_name, subscriber)
    except WebSocketDisconnect:
        pass
    finally:
        disconnect(chat_name, websocket)
