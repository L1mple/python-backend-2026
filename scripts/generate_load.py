"""Создаём запросы для графиков: python scripts/generate_load.py 120."""

import sys
import time

import httpx


def main():
    url = "http://127.0.0.1:28000"
    seconds = 120
    if len(sys.argv) > 1:
        seconds = int(sys.argv[1])

    count = 0
    with httpx.Client(base_url=url) as client:
        response = client.post("/item", json={"name": "Dashboard demo", "price": 25})
        response.raise_for_status()
        item = response.json()

        response = client.post("/cart")
        response.raise_for_status()
        cart = response.json()

        response = client.post(f"/cart/{cart['id']}/add/{item['id']}")
        response.raise_for_status()

        paths = ["/item", f"/item/{item['id']}", f"/cart/{cart['id']}", "/missing", "/item?limit=0"]
        for second in range(seconds):
            for path in paths:
                client.get(path)
                count += 1
            time.sleep(1)
    print(f"Sent {count} requests to {url}")


if __name__ == "__main__":
    main()
