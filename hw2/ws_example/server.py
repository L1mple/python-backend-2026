from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


@dataclass(slots=True)
class Broadcaster:
    subscribers: list[WebSocket] = field(default_factory=list)

    def subscribe(self, ws: WebSocket) -> None:
        self.subscribers.append(ws)

    def unsubscribe(self, ws: WebSocket) -> None:
        if ws in self.subscribers:
            self.subscribers.remove(ws)

    async def publish(self, message: str, sender: WebSocket) -> None:
        for ws in self.subscribers.copy():
            if ws == sender:
                continue
            try:
                await ws.send_text(message)
            except (WebSocketDisconnect, OSError, RuntimeError) as e:
                print(f"Error sending message: {e}")
                self.unsubscribe(ws)


rooms: dict[str, Broadcaster] = {}


@app.websocket("/chat/{chat_name}")
async def chat(ws: WebSocket, chat_name: str) -> None:
    await ws.accept()

    if chat_name not in rooms:
        rooms[chat_name] = Broadcaster()
    room = rooms[chat_name]
    room.subscribe(ws)
    print(f"Room {chat_name!r}, connections: {len(room.subscribers)}")
    username = f"user_{uuid4().hex[:8]}"

    print(f"[{chat_name}] {username} connected")
    try:
        while True:
            text = await ws.receive_text()
            if not text.strip():
                continue

            message = f"{username} :: {text}"
            await room.publish(message, sender=ws)
    except WebSocketDisconnect:
        pass
    finally:
        room.unsubscribe(ws)
        if not room.subscribers and rooms.get(chat_name) is room:
            del rooms[chat_name]
        print(f"[{chat_name}] {username} disconnected")
