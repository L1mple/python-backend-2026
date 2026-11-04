"""Простой генератор нагрузки для Shop API (только стандартная библиотека).

Нужен, чтобы на дашбордах Grafana появились данные: создает товары и корзины,
читает, меняет, удаляет и иногда шлет заведомо некорректные запросы
(404 и 422), чтобы были видны ответы разных классов.

Запуск:
    python load.py                       # бесконечно, на http://localhost:8080
    python load.py --duration 120        # остановиться через 2 минуты
    python load.py --url http://shop-api:8080 --threads 8
"""

import argparse
import json
import random
import threading
import time
import urllib.error
import urllib.request


def call(base_url: str, method: str, path: str, body=None) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base_url + path,
        data=data,
        method=method,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, TimeoutError):
        return 0, None


def worker(base_url: str, stop: threading.Event) -> None:
    item_ids: list[int] = []
    cart_ids: list[int] = []

    while not stop.is_set():
        action = random.random()

        if action < 0.15 or not item_ids:
            status, item = call(
                base_url,
                "POST",
                "/item",
                {"name": f"Товар {random.randint(1, 10_000)}", "price": round(random.uniform(10, 500), 2)},
            )
            if status == 201 and item:
                item_ids.append(item["id"])
        elif action < 0.25 or not cart_ids:
            status, cart = call(base_url, "POST", "/cart")
            if status == 201 and cart:
                cart_ids.append(cart["id"])
        elif action < 0.45:
            call(base_url, "POST", f"/cart/{random.choice(cart_ids)}/add/{random.choice(item_ids)}")
        elif action < 0.60:
            call(base_url, "GET", f"/cart/{random.choice(cart_ids)}")
        elif action < 0.70:
            call(base_url, "GET", f"/item/{random.choice(item_ids)}")
        elif action < 0.78:
            call(base_url, "GET", f"/item?limit={random.randint(1, 20)}&min_price={random.randint(0, 200)}")
        elif action < 0.84:
            call(base_url, "GET", f"/cart?limit={random.randint(1, 20)}&min_quantity={random.randint(0, 3)}")
        elif action < 0.88:
            call(base_url, "PATCH", f"/item/{random.choice(item_ids)}", {"price": round(random.uniform(10, 500), 2)})
        elif action < 0.90:
            call(base_url, "DELETE", f"/item/{item_ids.pop(random.randrange(len(item_ids)))}")
        elif action < 0.95:
            call(base_url, "GET", f"/item/{random.randint(100_000, 200_000)}")  # 404
        else:
            call(base_url, "GET", "/item?limit=0")  # 422

        time.sleep(random.uniform(0.01, 0.1))


def main() -> None:
    parser = argparse.ArgumentParser(description="Load generator for Shop API")
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--duration", type=float, default=0, help="seconds, 0 = run until interrupted")
    args = parser.parse_args()

    stop = threading.Event()
    threads = [threading.Thread(target=worker, args=(args.url, stop), daemon=True) for _ in range(args.threads)]
    for thread in threads:
        thread.start()

    print(f"Generating load on {args.url} with {args.threads} threads (Ctrl+C to stop)")
    try:
        stop.wait(args.duration or None)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()


if __name__ == "__main__":
    main()
