from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

chats: dict[str, list[WebSocket]] = {}


@router.websocket('/chat/{chat_name}')
async def chat(ws: WebSocket, chat_name: str):
    await ws.accept()
    username = str(uuid4())

    if chat_name not in chats:
        chats[chat_name] = []
    chats[chat_name].append(ws)

    try:
        while True:
            message = await ws.receive_text()
            text = f'{username} :: {message}'
            for client in chats[chat_name]:
                await client.send_text(text)
    except WebSocketDisconnect:
        chats[chat_name].remove(ws)
        if not chats[chat_name]:
            del chats[chat_name]
