import random
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from faker import Faker

BASE_URL = "http://localhost:8080"
DURATION_SECONDS = 180
WORKERS = 10

faker = Faker()


def worker() -> None:
    item_ids: list[int] = []
    cart_ids: list[int] = []
    deadline = time.time() + DURATION_SECONDS

    with httpx.Client(base_url=BASE_URL, trust_env=False) as client:
        while time.time() < deadline:
            action = random.random()

            if action < 0.2 or not item_ids:
                body = {
                    "name": faker.word(),
                    "price": round(random.uniform(1, 1000), 2),
                }
                item_ids.append(client.post("/item", json=body).json()["id"])
            elif action < 0.35:
                client.get(f"/item/{random.choice(item_ids)}")
            elif action < 0.45:
                client.get("/item", params={"limit": 20, "max_price": 500})
            elif action < 0.5:
                client.patch(f"/item/{random.choice(item_ids)}", json={"price": 1.0})
            elif action < 0.55:
                client.delete(f"/item/{item_ids.pop(random.randrange(len(item_ids)))}")
            elif action < 0.65 or not cart_ids:
                cart_ids.append(client.post("/cart").json()["id"])
            elif action < 0.8:
                client.post(
                    f"/cart/{random.choice(cart_ids)}/add/{random.choice(item_ids)}"
                )
            elif action < 0.9:
                client.get(f"/cart/{random.choice(cart_ids)}")
            elif action < 0.95:
                client.get(f"/item/{random.randint(10**6, 10**7)}")
            else:
                client.post("/item", json={"name": "broken"})


with ThreadPoolExecutor(WORKERS) as executor:
    futures = [executor.submit(worker) for _ in range(WORKERS)]
    for future in futures:
        future.result()

print("done")
