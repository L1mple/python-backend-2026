"""Send demo requests to the local Shop API to populate Grafana dashboards."""

import argparse
import json
import random
import time
from collections import Counter
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(base_url: str, path: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(
        base_url + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration", type=float, default=180, help="Duration in seconds")
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")
    base_url = args.base_url.rstrip("/")
    _, item = request(base_url, "/item", "POST", {"name": "Demo item", "price": 100})
    _, cart = request(base_url, "/cart", "POST")
    operations = [
        ("/item", "GET", None),
        (f"/item/{item['id']}", "GET", None),
        ("/cart", "GET", None),
        (f"/cart/{cart['id']}/add/{item['id']}", "POST", None),
        ("/item/0", "GET", None),
        ("/item", "POST", {"name": "Invalid price", "price": -1}),
    ]
    statuses: Counter[int] = Counter()
    deadline = time.monotonic() + args.duration
    while time.monotonic() < deadline:
        status, _ = request(base_url, *random.choice(operations))
        statuses[status] += 1
        time.sleep(random.uniform(0.03, 0.25))
    print(f"Sent {sum(statuses.values())} requests: {dict(sorted(statuses.items()))}")


if __name__ == "__main__":
    main()
