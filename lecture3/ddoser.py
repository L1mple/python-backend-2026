import random
import time
from concurrent.futures import ThreadPoolExecutor

import requests

URL = "http://localhost:8080"
WORKERS = 10
DURATION = 60

items = []
carts = []


def work(deadline):
    s = requests.Session()
    while time.time() < deadline:
        action = random.choice(["item", "get_item", "list", "cart", "add", "bad"])

        if action == "item":
            r = s.post(f"{URL}/item", json={"name": "x", "price": random.randint(1, 1000)})
            items.append(r.json()["id"])
        elif action == "get_item" and items:
            s.get(f"{URL}/item/{random.choice(items)}")
        elif action == "list":
            s.get(f"{URL}/item", params={"limit": 50})
            s.get(f"{URL}/cart", params={"limit": 50})
        elif action == "cart":
            r = s.post(f"{URL}/cart")
            carts.append(r.json()["id"])
        elif action == "add" and items and carts:
            s.post(f"{URL}/cart/{random.choice(carts)}/add/{random.choice(items)}")
        elif action == "bad":
            s.get(f"{URL}/item/999999")


deadline = time.time() + DURATION
with ThreadPoolExecutor(WORKERS) as ex:
    for _ in range(WORKERS):
        ex.submit(work, deadline)
