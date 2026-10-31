import asyncio
import websockets

async def test_isolation():
    uri1 = "ws://127.0.0.1:8000/chat/room_A"
    uri2 = "ws://127.0.0.1:8000/chat/room_B"

    async with websockets.connect(uri1) as ws_a1, websockets.connect(uri1) as ws_a2:
        async with websockets.connect(uri2) as ws_b1:
            await ws_a1.send("Сообщение для А")

            msg_a1 = await ws_a1.recv()
            msg_a2 = await ws_a2.recv()
            assert " :: Сообщение для А" in msg_a1
            assert " :: Сообщение для А" in msg_a2

            try:
                await asyncio.wait_for(ws_b1.recv(), timeout=0.5)
                raise AssertionError("Пользователь из другой комнаты получил сообщение!")
            except asyncio.TimeoutError:
                pass

    print("Тест пройден успешно!")

if __name__ == "__main__":
    asyncio.run(test_isolation())