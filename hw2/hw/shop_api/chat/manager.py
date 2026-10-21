from collections import defaultdict

from secrets import token_hex

from fastapi import WebSocket


class ChatManager:

    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._usernames: dict[WebSocket, str] = {}

    async def connect(self, chat_name: str, ws: WebSocket) -> str:
        await ws.accept()

        username = f"user-{token_hex(4)}"  # :TODO: see
        self._rooms[chat_name].add(ws)
        self._usernames[ws] = username

        return username

    def disconnect(self, chat_name: str, ws: WebSocket) -> None:
        room = self._rooms.get(chat_name)
        if room is not None:
            room.discard(ws)
            if not room:
                self._rooms.pop(chat_name, None)

        self._usernames.pop(ws, None)

    async def broadcast(
            self,
            chat_name: str,
            message: str,
            sender: WebSocket
    ) -> None:
        room = self._rooms.get(chat_name)
        if not room:
            return

        dead_connections: list[WebSocket] = []

        for connection in room:
            if connection is sender:
                continue

            try:
                await connection.send_text(message)
            except RuntimeError:
                dead_connections.append(connection)

        for connection in dead_connections:
            self.disconnect(chat_name, connection)


chat_manager = ChatManager()
