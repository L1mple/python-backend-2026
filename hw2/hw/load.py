# гоняет запросы в сервис, чтобы на графиках что-то было
import random

import httpx

client = httpx.Client(base_url="http://localhost:8000")

item_ids = [
    client.post("/item", json={"name": f"item {i}", "price": random.uniform(10, 500)}).json()["id"]
    for i in range(20)
]

for _ in range(3000):
    cart_id = client.post("/cart").json()["id"]
    client.post(f"/cart/{cart_id}/add/{random.choice(item_ids)}")
    client.get(f"/cart/{cart_id}")
    client.get("/item", params={"limit": 5})
    client.get(f"/item/{random.randint(1, 30)}")  # иногда 404
