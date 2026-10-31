from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter(prefix="/chat")


rooms: dict[str, dict[WebSocket, str]] = {}


def generate_username() -> str:
    return f"user-{uuid4().hex[:8]}"


@router.websocket("/{chat_name}")
async def chat(
    websocket: WebSocket,
    chat_name: str,
) -> None:
    await websocket.accept()

    username = generate_username()

    if chat_name not in rooms:
        rooms[chat_name] = {}

    rooms[chat_name][websocket] = username

    try:
        while True:
            message = await websocket.receive_text()

            formatted_message = f"{username} :: {message}"

            for client in list(rooms[chat_name]):
                if client is websocket:
                    continue

                await client.send_text(formatted_message)

    except WebSocketDisconnect:
        rooms[chat_name].pop(websocket, None)

        if not rooms[chat_name]:
            del rooms[chat_name]