import argparse
import time
from concurrent.futures import ThreadPoolExecutor

import requests


def send_request(session, method, path, expected_status, **kwargs):
    response = session.request(
        method,
        f"http://localhost:8080{path}",
        timeout=10,
        **kwargs,
    )
    if response.status_code != expected_status:
        raise RuntimeError(
            f"{method} {path}: expected {expected_status}, "
            f"got {response.status_code}: {response.text}"
        )
    return response


def create_items(session):
    item_ids = []
    for index in range(5):
        response = send_request(
            session,
            "POST",
            "/item",
            201,
            json={"name": f"Demo item {index}", "price": 100 + index * 10},
        )
        item_ids.append(response.json()["id"])
    return item_ids


def create_cart(session, item_ids):
    response = send_request(session, "POST", "/cart", 201)
    cart_id = response.json()["id"]
    for item_id in item_ids:
        send_request(session, "POST", f"/cart/{cart_id}/add/{item_id}", 200)
    return cart_id


def run_client(item_ids, cart_id, duration):
    deadline = time.monotonic() + duration
    requests_count = 0

    with requests.Session() as session:
        while time.monotonic() < deadline:
            send_request(session, "GET", "/item", 200)
            send_request(session, "GET", f"/item/{item_ids[0]}", 200)
            send_request(session, "GET", "/cart", 200)
            send_request(session, "GET", f"/cart/{cart_id}", 200)
            send_request(session, "GET", "/item/0", 404)
            send_request(session, "GET", "/item", 422, params={"limit": 0})
            requests_count += 6
            time.sleep(0.2)

    return requests_count


def main():
    parser = argparse.ArgumentParser(description="Generate traffic for Shop API dashboards")
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.duration <= 0 or args.workers <= 0:
        parser.error("duration and workers must be positive")

    with requests.Session() as session:
        item_ids = create_items(session)
        cart_id = create_cart(session, item_ids)

    print(f"Generating traffic for {args.duration} seconds with {args.workers} workers...")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(run_client, item_ids, cart_id, args.duration)
            for _ in range(args.workers)
        ]
        requests_count = sum(future.result() for future in futures)
    print(f"Completed {requests_count} requests (including expected 404 and 422 responses).")


if __name__ == "__main__":
    main()
