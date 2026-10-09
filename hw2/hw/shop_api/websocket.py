from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()


@dataclass
class Chat:
    users: list[WebSocket] = field(default_factory=list)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.users.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.users.remove(websocket)

    async def send_message(self, sender: WebSocket, message: str):
        for user in self.users:
            if user != sender:
                await user.send_text(message)


chats: dict[str, Chat] = {}


@router.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str):
    username = uuid4().hex[:8]

    if chat_name not in chats:
        chats[chat_name] = Chat()

    current_chat = chats[chat_name]
    await current_chat.connect(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            await current_chat.send_message(
                websocket,
                f"{username} :: {message}",
            )
    except WebSocketDisconnect:
        current_chat.disconnect(websocket)
        if not current_chat.users:
            del chats[chat_name]
