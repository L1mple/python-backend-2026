from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["chat"])


@dataclass(slots=True)
class Broadcaster:
    rooms: dict[str, dict[str, WebSocket]] = field(
        init=False, default_factory=dict
    )

    async def subscribe(self, chat_name: str, ws: WebSocket) -> str:
        await ws.accept()
        username = uuid4().hex[:8]
        self.rooms.setdefault(chat_name, {})[username] = ws
        return username

    def unsubscribe(self, chat_name: str, username: str) -> None:
        room = self.rooms.get(chat_name)
        if room is None:
            return
        room.pop(username, None)
        if not room:
            self.rooms.pop(chat_name, None)

    async def publish(
        self, chat_name: str, sender: str, message: str
    ) -> None:
        for username, ws in list(self.rooms.get(chat_name, {}).items()):
            if username == sender:
                continue
            try:
                await ws.send_text(f"{sender} :: {message}")
            except Exception:
                pass


broadcaster = Broadcaster()


@router.websocket("/chat/{chat_name}")
async def ws_chat(ws: WebSocket, chat_name: str):
    username = await broadcaster.subscribe(chat_name, ws)
    try:
        while True:
            text = await ws.receive_text()
            await broadcaster.publish(chat_name, username, text)
    except WebSocketDisconnect:
        broadcaster.unsubscribe(chat_name, username)