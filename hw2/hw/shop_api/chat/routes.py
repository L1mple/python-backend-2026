from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .manager import chat_manager

router = APIRouter()

@router.websocket("/{chat_name}")
async def chat(ws: WebSocket, chat_name: str) -> None:
    username = await chat_manager.connect(chat_name, ws)

    try:
        while True:
            message = await ws.receive_text()
            await chat_manager.broadcast(
                chat_name,
                f"{username} :: {message}",
                ws,
            )
    except WebSocketDisconnect:
        pass
    finally:
        chat_manager.disconnect(chat_name, ws)