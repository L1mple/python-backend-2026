from collections import defaultdict
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["chat"])

# Название чата -> подключённые к нему клиенты
_rooms: dict[str, list[WebSocket]] = defaultdict(list)


@router.websocket("/chat/{chat_name}")
async def chat(ws: WebSocket, chat_name: str) -> None:
    await ws.accept()
    username = f"user-{uuid4().hex[:8]}"
    room = _rooms[chat_name]
    room.append(ws)

    try:
        while True:
            message = await ws.receive_text()
            # Копия списка: пока идёт рассылка, кто-то может отключиться
            for other in list(room):
                if other is not ws:
                    await other.send_text(f"{username} :: {message}")
    except WebSocketDisconnect:
        room.remove(ws)
        if not room:
            del _rooms[chat_name]
