import asyncio
import random
import time

import httpx

BASE_URL = "http://localhost:8080"

# Настройки нагрузки
WORKERS = 5
DURATION_SECONDS = 60


async def worker(client: httpx.AsyncClient, worker_id: int):
    while True:
        try:
            response = await client.post(
                "/item",
                json={
                    "name": f"Test item {worker_id}-{random.randint(1, 999999)}",
                    "price": round(random.uniform(10, 1000), 2),
                },
            )
            response.raise_for_status()
            item = response.json()
            item_id = item["id"]
            await client.get("/item")
            await client.get(f"/item/{item_id}")

            response = await client.post("/cart")
            response.raise_for_status()
            cart_id = response.json()["id"]

            await client.get("/cart")

            await client.post(f"/cart/{cart_id}/add/{item_id}")

            await client.get(f"/cart/{cart_id}")

            await client.put(
                f"/item/{item_id}",
                json={
                    "name": f"Updated item {item_id}",
                    "price": round(random.uniform(10, 1000), 2),
                },
            )
            await client.patch(
                f"/item/{item_id}",
                json={"price": round(random.uniform(10, 1000), 2)},
            )

            await client.delete(f"/item/{item_id}")

            await client.get("/item/999999999")

            await client.get("/cart/999999999")

        except httpx.HTTPError as exc:
            print(f"[worker {worker_id}] HTTP error: {exc}")

        await asyncio.sleep(0.05)


async def main():
    deadline = time.monotonic() + DURATION_SECONDS
    timeout = httpx.Timeout(10.0)

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=timeout,
    ) as client:
        tasks = [
            asyncio.create_task(worker(client, i))
            for i in range(WORKERS)
        ]

        print(
            f"Generating traffic for {DURATION_SECONDS}s "
            f"with {WORKERS} workers against {BASE_URL}"
        )

        try:
            while time.monotonic() < deadline:
                await asyncio.sleep(0.2)
        finally:
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

    print("Load test finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")
