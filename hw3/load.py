import argparse
import json
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(
    base_url: str,
    path: str,
    method: str = "GET",
    body: dict[str, str | int] | None = None,
) -> tuple[int, Any]:
    """Отправить запрос, включая ожидаемые ошибки для графиков Grafana."""
    data = None if body is None else json.dumps(body).encode()
    req = Request(
        base_url + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=5) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except HTTPError as error:
        error.close()
        return error.code, None


def main() -> None:
    """Создать товар и корзину, затем генерировать HTTP-нагрузку заданное время."""
    parser = argparse.ArgumentParser(description="Нагрузка для дашбордов HW3")
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--duration", type=float, default=180)
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args()
    if args.duration <= 0 or args.interval <= 0:
        parser.error("duration и interval должны быть положительными")

    base_url = args.url.rstrip("/")
    status, item = request(
        base_url, "/item", "POST", {"name": "HW3 demo", "price": 100}
    )
    if status != 201:
        raise RuntimeError(f"Не удалось создать товар: HTTP {status}")
    status, cart = request(base_url, "/cart", "POST")
    if status != 201:
        raise RuntimeError(f"Не удалось создать корзину: HTTP {status}")
    request(base_url, f"/cart/{cart['id']}/add/{item['id']}", "POST")

    paths = [
        "/item",
        f"/item/{item['id']}",
        "/cart",
        f"/cart/{cart['id']}",
        "/item/0",
        "/item?limit=0",
    ]
    counts: dict[int, int] = {}
    deadline = time.monotonic() + args.duration
    index = 0
    while time.monotonic() < deadline:
        status, _ = request(base_url, paths[index % len(paths)])
        counts[status] = counts.get(status, 0) + 1
        index += 1
        time.sleep(args.interval)
    print(f"Запросов: {index}. Ответы по статусам: {counts}")


if __name__ == "__main__":
    main()
