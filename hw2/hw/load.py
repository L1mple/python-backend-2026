"""Нагрузка на Shop API, чтобы на дашбордах Grafana было что смотреть.

Сервис должен быть запущен (docker compose up). Запуск:

    python load.py --duration 180 --users 10
"""

import argparse
import asyncio
import random
import time

import httpx
import websockets


async def shopper(client: httpx.AsyncClient, item_ids: list[int], deadline: float) -> None:
    while time.monotonic() < deadline:
        cart_id = (await client.post("/cart")).json()["id"]
        for item_id in random.sample(item_ids, k=random.randint(1, 5)):
            await client.post(f"/cart/{cart_id}/add/{item_id}")

        await client.get(f"/cart/{cart_id}")
        await client.get("/cart", params={"min_price": round(random.uniform(0, 500), 2)})
        await client.get("/item", params={"limit": 20, "offset": random.randint(0, 30)})

        # Немного ошибочных запросов, чтобы на графике кодов были не только 2xx
        if random.random() < 0.2:
            await client.get(f"/item/{random.randint(100_000, 200_000)}")  # 404
        if random.random() < 0.1:
            await client.get("/item", params={"limit": 0})  # 422

        await asyncio.sleep(random.uniform(0.05, 0.3))


async def editor(client: httpx.AsyncClient, item_ids: list[int], deadline: float) -> None:
    while time.monotonic() < deadline:
        response = await client.post(
            "/item",
            json={"name": f"Новинка {random.randint(1, 999)}", "price": round(random.uniform(10, 500), 2)},
        )
        item_ids.append(response.json()["id"])

        await client.patch(f"/item/{random.choice(item_ids)}", json={"price": round(random.uniform(10, 500), 2)})

        # Удалённые товары остаются в списке: покупатели будут получать на них 404
        if random.random() < 0.3:
            await client.delete(f"/item/{random.choice(item_ids)}")

        await asyncio.sleep(random.uniform(0.5, 1.5))


async def chatter(ws_url: str, room: str, deadline: float) -> None:
    # Клиенты подключаются и уходят в разное время, чтобы график чатов менялся
    await asyncio.sleep(random.uniform(0, 30))
    leave_at = min(deadline, time.monotonic() + random.uniform(30, 150))

    async with websockets.connect(f"{ws_url}/chat/{room}") as ws:
        # Входящие сообщения читаем, иначе они копятся в буфере
        reader = asyncio.create_task(drain(ws))
        while time.monotonic() < leave_at:
            await ws.send(f"привет из комнаты {room}")
            await asyncio.sleep(random.uniform(1, 3))
        reader.cancel()


async def drain(ws) -> None:
    async for _ in ws:
        pass


async def main(base_url: str, duration: float, users: int) -> None:
    deadline = time.monotonic() + duration
    ws_url = base_url.replace("http", "ws", 1)

    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        item_ids = []
        for i in range(30):
            response = await client.post(
                "/item",
                json={"name": f"Товар {i}", "price": round(random.uniform(10, 500), 2)},
            )
            item_ids.append(response.json()["id"])

        await asyncio.gather(
            *(shopper(client, item_ids, deadline) for _ in range(users)),
            editor(client, item_ids, deadline),
            *(chatter(ws_url, random.choice(["general", "sale"]), deadline) for _ in range(8)),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--duration", type=float, default=180, help="секунд")
    parser.add_argument("--users", type=int, default=10, help="одновременных покупателей")
    args = parser.parse_args()

    asyncio.run(main(args.url, args.duration, args.users))
