from dataclasses import dataclass, field
from uuid import uuid4
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from collections import defaultdict

app = FastAPI()


@dataclass(slots=True)
class Broadcaster:
    subscribers: defaultdict[str, list[WebSocket]] = field(init=False, default_factory=lambda: defaultdict(list))

    async def subscribe(self, ws: WebSocket, chat: str) -> None:
        await ws.accept()
        self.subscribers[chat].append(ws)

    async def unsubscribe(self, ws: WebSocket, chat: str) -> None:
        chat_subscribers = self.subscribers.get(chat)
        if chat_subscribers is None:
            return
        if ws in chat_subscribers:
            chat_subscribers.remove(ws)
        if len(chat_subscribers) == 0:
            self.subscribers.pop(chat)

    async def publish(self, message: str, chat: str) -> None:
        for ws in self.subscribers.get(chat, []):
            await ws.send_text(message)


broadcaster = Broadcaster()


@app.websocket("/chat/{chat_name}")
async def ws_chat(ws: WebSocket, chat_name: str) -> None:
    username = f"user{uuid4()}"
    await broadcaster.subscribe(ws, chat_name)
    await broadcaster.publish(f"Client {username} subscribed", chat_name)

    try:
        while True:
            text = await ws.receive_text()
            await broadcaster.publish(f"{username} :: {text}", chat_name)
    except WebSocketDisconnect:
        await broadcaster.unsubscribe(ws, chat_name)
        await broadcaster.publish(f"Client {username} unsubscribed", chat_name)
