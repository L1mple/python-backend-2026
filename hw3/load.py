import argparse
import json
import random
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(base_url: str, path: str, method: str = "GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = Request(base_url + path, data=data, headers=headers, method=method)
    with urlopen(req, timeout=5) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate traffic for the Shop API dashboards")
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--duration", type=float, default=120)
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args()
    if args.duration <= 0 or args.interval <= 0:
        parser.error("duration and interval must be positive")
    base_url = args.url.rstrip("/")

    item = request(base_url, "/item", "POST", {"name": "Bread", "price": 35.5})
    cart = request(base_url, "/cart", "POST")
    item_id, cart_id = item["id"], cart["id"]
    actions = [
        ("GET", "/item"),
        ("GET", "/cart"),
        ("GET", f"/item/{item_id}"),
        ("GET", f"/cart/{cart_id}"),
        ("POST", f"/cart/{cart_id}/add/{item_id}"),
        ("GET", "/item/999999999"),
        ("GET", "/item?limit=0"),
    ]
    deadline = time.monotonic() + args.duration
    sent, errors = 0, 0
    while time.monotonic() < deadline:
        method, path = random.choices(actions, weights=[3, 2, 3, 2, 1, 1, 1])[0]
        try:
            request(base_url, path, method)
        except HTTPError as error:
            error.close()
            if error.code not in (404, 422):
                raise
            errors += 1
        sent += 1
        time.sleep(args.interval)
    print(f"Sent {sent} requests, including {errors} expected 404/422 responses")


if __name__ == "__main__":
    main()
