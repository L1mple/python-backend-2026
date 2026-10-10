from uuid import uuid4

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
)

chat_router = APIRouter()


class ChatRoomsBroadcaster:
    def __init__(self) -> None:
        self.websockets_by_chat_name: dict[str, list[WebSocket]] = {}

    async def accept_and_join_chat(
        self,
        chat_name: str,
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()
        if chat_name not in self.websockets_by_chat_name:
            self.websockets_by_chat_name[chat_name] = []
        self.websockets_by_chat_name[chat_name].append(websocket)

    def leave_chat(
        self,
        chat_name: str,
        websocket: WebSocket,
    ) -> None:
        websockets_in_chat = self.websockets_by_chat_name.get(chat_name)
        if websockets_in_chat is None or websocket not in websockets_in_chat:
            return
        websockets_in_chat.remove(websocket)
        if not websockets_in_chat:
            del self.websockets_by_chat_name[chat_name]

    async def send_message_to_other_members_of_chat(
        self,
        chat_name: str,
        sender_websocket: WebSocket,
        message: str,
    ) -> None:
        websockets_in_chat_before_sending = list(self.websockets_by_chat_name.get(chat_name) or [])
        for websocket in websockets_in_chat_before_sending:
            if websocket is sender_websocket:
                continue
            try:
                await websocket.send_text(message)
            except (WebSocketDisconnect, RuntimeError, OSError):
                self.leave_chat(
                    chat_name=chat_name,
                    websocket=websocket,
                )


chat_rooms_broadcaster = ChatRoomsBroadcaster()


@chat_router.websocket("/chat/{chat_name}")
async def join_chat_and_relay_messages_to_other_members(
    websocket: WebSocket,
    chat_name: str,
) -> None:
    random_username = f"user-{uuid4().hex[:8]}"
    await chat_rooms_broadcaster.accept_and_join_chat(
        chat_name=chat_name,
        websocket=websocket,
    )
    try:
        while True:
            message = await websocket.receive_text()
            await chat_rooms_broadcaster.send_message_to_other_members_of_chat(
                chat_name=chat_name,
                sender_websocket=websocket,
                message=f"{random_username} :: {message}",
            )
    except WebSocketDisconnect:
        chat_rooms_broadcaster.leave_chat(
            chat_name=chat_name,
            websocket=websocket,
        )
