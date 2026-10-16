from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from shop_api.deps import ChatServiceDep

router = APIRouter()


@router.get('/chat')
async def chat_page():
    return FileResponse(Path(__file__).parent.parent / 'static' / 'chat.html')


@router.websocket('/chat/{chat_name}')
async def connect_to_chat(chat_name: str,
                          ws: WebSocket,
                          chat_service: ChatServiceDep):
    username = chat_service.generate_username()
    await chat_service.subscribe(chat_name, ws)

    try:
        while True:
            message = await ws.receive_text()
            await chat_service.publish(chat_name, username, message)
    except WebSocketDisconnect:
        chat_service.unsubscribe(chat_name, ws)
