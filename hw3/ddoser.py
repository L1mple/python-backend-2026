import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen


def request(base_url, method, path, body=None):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = Request(base_url.rstrip("/") + path, data=payload, headers=headers, method=method)
    with urlopen(req, timeout=5) as response:
        content = response.read()
    return json.loads(content) if content else {}


def pause(started):
    time.sleep(0.1 if int((time.monotonic() - started) // 12) % 2 == 0 else 0.5)


def send_requests(base_url, started, deadline, worker_id):
    cart_id = request(base_url, "POST", "/cart")["id"]
    item_ids = [
        request(base_url, "POST", "/item", {"name": f"Товар {worker_id}", "price": 100})["id"]
    ]
    actions = (
        "list_items",
        "get_item",
        "create_item",
        "replace_item",
        "patch_item",
        "list_carts",
        "get_cart",
        "add_to_cart",
    )
    sent = 2
    while time.monotonic() < deadline:
        action = random.choice(actions + (("delete_item",) if len(item_ids) > 1 else ()))
        item_id = random.choice(item_ids)
        match action:
            case "list_items":
                request(base_url, "GET", "/item?min_price=50&limit=5")
            case "get_item":
                request(base_url, "GET", f"/item/{item_id}")
            case "create_item":
                item_ids.append(request(
                    base_url, "POST", "/item",
                    {"name": f"Товар {worker_id}-{sent}", "price": random.randint(50, 500)},
                )["id"])
            case "replace_item":
                request(base_url, "PUT", f"/item/{item_id}", {"name": "Товар дня", "price": 90})
            case "patch_item":
                request(base_url, "PATCH", f"/item/{item_id}", {"price": random.randint(50, 500)})
            case "delete_item":
                request(base_url, "DELETE", f"/item/{item_id}")
                item_ids.remove(item_id)
            case "list_carts":
                request(base_url, "GET", "/cart?min_quantity=1")
            case "get_cart":
                request(base_url, "GET", f"/cart/{cart_id}")
            case "add_to_cart":
                request(base_url, "POST", f"/cart/{cart_id}/add/{item_id}")
        sent += 1
        pause(started)
    return sent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--duration", type=int, default=60)
    args = parser.parse_args()

    started = time.monotonic()
    deadline = started + args.duration
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(send_requests, args.base_url, started, deadline, worker_id): f"worker-{worker_id}"
            for worker_id in range(4)
        }
        for future in as_completed(futures):
            print(f"{futures[future]}: {future.result()} requests")


if __name__ == "__main__":
    main()
