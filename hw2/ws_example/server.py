import random
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

ADJECTIVES = ["Brave", "Sleepy", "Happy", "Grumpy", "Swift", "Silent", "Clever", "Lazy"]
ANIMALS = ["Otter", "Fox", "Panda", "Owl", "Cat", "Badger", "Koala", "Wolf"]


def generate_name() -> str:
    return (
        f"{random.choice(ADJECTIVES)}{random.choice(ANIMALS)}{random.randint(10, 99)}"
    )


@dataclass(slots=True)
class Broadcaster:
    rooms: dict[str, list[WebSocket]] = field(
        init=False, default_factory=lambda: defaultdict(list)
    )

    async def subscribe(self, ws: WebSocket, chat_name: str) -> None:
        await ws.accept()
        self.rooms[chat_name].append(ws)

    async def unsubscribe(
        self, ws: WebSocket, chat_name: str, client_name: str
    ) -> None:
        self.rooms[chat_name].remove(ws)
        if not self.rooms[chat_name]:
            del self.rooms[chat_name]
        else:
            await self.publish(f"{client_name} left '{chat_name}'", chat_name)

    async def publish(
        self, message: str, chat_name: str, sender: WebSocket | None = None
    ) -> None:
        for ws in self.rooms.get(chat_name, []):
            if ws is not sender:
                await ws.send_text(message)


broadcaster = Broadcaster()


@app.websocket("/chat/{chat_name}")
async def chat(ws: WebSocket, chat_name: str):
    client_name = generate_name()
    await broadcaster.subscribe(ws, chat_name)
    await broadcaster.publish(
        f"{client_name} connect to '{chat_name}'", chat_name
    )

    try:
        while True:
            text = await ws.receive_text()
            await broadcaster.publish(f"{client_name} :: {text}", chat_name, ws)
    except WebSocketDisconnect:
        await broadcaster.unsubscribe(ws, chat_name, client_name)


# @app.post("/publish")
# async def post_publish(request: Request):
#     message = (await request.body()).decode()
#     await broadcaster.publish(message)


# @app.websocket("/subscribe")
# async def ws_subscribe(ws: WebSocket):
#     client_id = uuid4()
#     await broadcaster.subscribe(ws)
#     await broadcaster.publish(f"client {client_id} subscribed")

#     try:
#         while True:
#             text = await ws.receive_text()
#             await broadcaster.publish(text)
#     except WebSocketDisconnect:
#         await broadcaster.unsubscribe(ws)
#         await broadcaster.publish(f"client {client_id} unsubscribed")
