import random
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = "http://localhost:8080"
DURATION_SECONDS = 120
THREADS = 8


def worker() -> None:
    deadline = time.time() + DURATION_SECONDS
    with httpx.Client(base_url=BASE, timeout=5) as client:
        while time.time() < deadline:
            client.post(
                "/item",
                json={"name": "item", "price": round(random.uniform(10, 500), 2)},
            )
            cart_id = client.post("/cart").json()["id"]
            for _ in range(random.randint(1, 5)):
                client.post(f"/cart/{cart_id}/add/{random.randint(1, 50)}")
            client.get(f"/cart/{cart_id}")
            client.get(f"/item/{random.randint(1, 500)}")
            client.get("/item", params={"limit": 10})
            client.get("/cart", params={"limit": 10})
            client.post("/cart/999999/add/1")
            time.sleep(0.01)


if __name__ == "__main__":
    with ThreadPoolExecutor(THREADS) as executor:
        list(executor.map(lambda _: worker(), range(THREADS)))
    print("done")