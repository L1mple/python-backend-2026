"""
Небольшой генератор нагрузки для hw3.

Дашборды в Grafana останутся пустыми, если через сервис не прошло ни одного
запроса - этот скрипт просто бьёт по ручкам shop_api, чтобы в Prometheus
появились реальные метрики (RPS, задержки, коды ответов) перед тем как
снимать скриншот дашбордов.

Зависимостей, кроме стандартной библиотеки, не требует. Запускать после
`docker compose up --build` (из папки hw3):

    python traffic.py
"""
import json
import random
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:8080"


def _request(method: str, path: str, body: dict | None = None) -> int:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError as e:
        print(f"{method} {path} -> connection error: {e}")
        return 0


def create_items(n: int = 20) -> list[int]:
    ids = []
    for i in range(n):
        status = _request(
            "POST",
            "/item",
            {"name": f"Товар {i}", "price": round(random.uniform(10, 500), 2)},
        )
        print("POST /item ->", status)
    return ids


def hit_item_endpoints(rounds: int = 60) -> None:
    for _ in range(rounds):
        status = _request("GET", "/item", None)
        print("GET /item ->", status)
        # немного "плохих" запросов, чтобы на дашборде были и ошибки
        if random.random() < 0.15:
            status = _request("GET", "/item", None)
        status = _request("GET", f"/item/{random.randint(1, 9999)}")
        print("GET /item/{id} ->", status)


def hit_cart_endpoints(rounds: int = 60) -> None:
    for _ in range(rounds):
        status = _request("POST", "/cart")
        print("POST /cart ->", status)
        status = _request("GET", "/cart")
        print("GET /cart ->", status)


def main() -> None:
    print("Создаю товары...")
    create_items()

    print("Генерирую трафик (20 потоков)...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for i in range(10):
            futures.append(executor.submit(hit_item_endpoints, 40))
            futures.append(executor.submit(hit_cart_endpoints, 40))

        for future in as_completed(futures):
            future.result()

    print("Готово. Метрики доступны на http://localhost:8080/metrics")


if __name__ == "__main__":
    main()
