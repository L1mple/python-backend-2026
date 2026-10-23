from fastapi.testclient import TestClient

from shop_api.main import app

client = TestClient(app)


def test_chat_websocket() -> None:
    with client.websocket_connect('/chat/room-1') as ws1:
        with client.websocket_connect('/chat/room-1') as ws2:
            with client.websocket_connect('/chat/room-2') as ws3:
                ws1.send_text('msg room 1')
                msg1 = ws1.receive_text()
                msg2 = ws2.receive_text()
                ws3.send_text('msg room 2')
                msg3 = ws3.receive_text()

                assert msg1 == msg2
                assert ' :: msg room 1' in msg1
                assert ' :: msg room 2' in msg3
