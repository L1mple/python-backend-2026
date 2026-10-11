from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

router = APIRouter()
rooms: dict[str, set[WebSocket]] = {}


@router.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()
    username = f"user-{uuid4().hex}"
    room = rooms.setdefault(chat_name, set())
    room.add(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            for recipient in tuple(room):
                if recipient is websocket:
                    continue
                if (
                    recipient.application_state != WebSocketState.CONNECTED
                    or recipient.client_state != WebSocketState.CONNECTED
                ):
                    room.discard(recipient)
                    continue
                try:
                    await recipient.send_text(f"{username} :: {message}")
                except (WebSocketDisconnect, OSError):
                    room.discard(recipient)
    except WebSocketDisconnect:
        pass
    finally:
        room.discard(websocket)
        if not room and rooms.get(chat_name) is room:
            del rooms[chat_name]
