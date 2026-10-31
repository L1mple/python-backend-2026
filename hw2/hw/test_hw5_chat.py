import re

from fastapi.testclient import TestClient
from shop_api.main import app
from shop_api.chat.routes import rooms


def test_chat_messages():
     with TestClient(app) as client:
         with client.websocket_connect("/chat/test-room") as user1:
             with client.websocket_connect("/chat/test-room") as user2:
                 user1.send_text("hello")

                 message = user2.receive_text()

                 assert re.fullmatch(
                     r"user-[0-9a-f]{8} :: hello",
                     message,
                 )

                 user2.send_text("reply")

                 response = user1.receive_text()

                 assert response.endswith(" :: reply")

     assert "test-room" not in rooms


def test_separate_chat_rooms():
     with TestClient(app) as client:
         with client.websocket_connect("/chat/room-a") as a1:
             with client.websocket_connect("/chat/room-a") as a2:
                 with client.websocket_connect("/chat/room-b") as b1:
                     with client.websocket_connect("/chat/room-b") as b2:

                         assert len(rooms["room-a"]) == 2
                         assert len(rooms["room-b"]) == 2

                         a1.send_text("message-a")
                         received_a = a2.receive_text()

                         assert received_a.endswith(
                             " :: message-a"
                         )

                         b1.send_text("message-b")
                         received_b = b2.receive_text()

                         assert received_b.endswith(
                             " :: message-b"
                         )

     assert "room-a" not in rooms
     assert "room-b" not in rooms
