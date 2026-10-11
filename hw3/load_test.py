import argparse
import json
import random
import time
import urllib.error
import urllib.request


def request(method: str, url: str, body: dict[str, object] | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return json.load(response)
    except urllib.error.HTTPError:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate traffic for the Shop API dashboard")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()

    item_ids = [
        request(
            "POST",
            f"{args.url}/item",
            {"name": f"Товар {number}", "price": random.randint(50, 1000)},
        )["id"]
        for number in range(1, 11)
    ]
    cart_ids = [request("POST", f"{args.url}/cart")["id"] for _ in range(5)]

    deadline = time.monotonic() + args.seconds
    requests_count = 0

    while time.monotonic() < deadline:
        action = random.randrange(5)
        if action == 0:
            request("GET", f"{args.url}/item")
        elif action == 1:
            request("GET", f"{args.url}/cart")
        elif action == 2:
            request(
                "POST",
                f"{args.url}/cart/{random.choice(cart_ids)}/add/{random.choice(item_ids)}",
            )
        elif action == 3:
            request("GET", f"{args.url}/cart/{random.choice(cart_ids)}")
        else:
            request("GET", f"{args.url}/item/999999")

        requests_count += 1
        time.sleep(0.05)

    print(f"Отправлено запросов: {requests_count}")


if __name__ == "__main__":
    main()
