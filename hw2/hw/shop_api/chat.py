from collections import defaultdict
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# chat_name -> {websocket: username}
rooms: dict[str, dict[WebSocket, str]] = defaultdict(dict)


async def broadcast(chat_name: str, sender: WebSocket, message: str) -> None:
    for ws in rooms[chat_name]:
        # kendine geri gondermiyoruz
        if ws is not sender:
            await ws.send_text(message)


@router.websocket("/chat/{chat_name}")
async def chat(ws: WebSocket, chat_name: str) -> None:
    await ws.accept()
    username = f"user-{uuid4().hex[:6]}"
    rooms[chat_name][ws] = username

    try:
        while True:
            text = await ws.receive_text()
            await broadcast(chat_name, ws, f"{username} :: {text}")
    except WebSocketDisconnect:
        del rooms[chat_name][ws]
        if not rooms[chat_name]:
            del rooms[chat_name]
