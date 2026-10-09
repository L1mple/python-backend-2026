import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:8000"


def request(path: str, method: str = "GET", payload: dict | None = None) -> None:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=3) as response:
            response.read()
    except HTTPError as exc:
    
        if exc.code != 404:
            raise


if __name__ == "__main__":
    for index in range(120):
        request("/item")
        request("/cart")
        request("/cart", "POST")
        request("/item", "POST", {"name": f"Товар {index}", "price": 99.9 + index})
        if index % 5 == 0:
            request("/item/999999")
        time.sleep(0.1)
    print("Готово: тестовые HTTP-запросы отправлены.")
