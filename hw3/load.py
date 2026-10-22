"""Нагрузка на Shop API, чтобы на дашбордах Grafana появились графики.

Запуск: python load.py  (сервис должен быть поднят на localhost:8080)
Создаёт товары и корзины, кладёт товары в корзины, часть запросов — заведомо с ошибкой 404.
"""

import random
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "http://localhost:8080"


def worker(n: int) -> None:
    for _ in range(200):
        item = requests.post(
            f"{BASE}/item", json={"name": f"item-{n}", "price": random.uniform(1, 100)}
        ).json()
        cart_id = requests.post(f"{BASE}/cart").json()["id"]
        requests.post(f"{BASE}/cart/{cart_id}/add/{item['id']}")
        requests.get(f"{BASE}/cart/{cart_id}")
        requests.get(f"{BASE}/item", params={"limit": 5})
        # ~10% "плохих" запросов: несуществующий товар -> 404
        if random.random() < 0.1:
            requests.get(f"{BASE}/item/999999")


with ThreadPoolExecutor(max_workers=10) as pool:
    list(pool.map(worker, range(10)))

print("done")
