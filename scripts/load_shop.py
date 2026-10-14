import argparse
import time

import httpx


class ShopLoad:
    """Bounded shop workload with one reusable item and cart."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def run(self, duration: float, interval: float):
        if not 0 < duration <= 3600 or not 0.01 <= interval <= 60:
            raise ValueError("duration must be (0, 3600], interval must be [0.01, 60]")
        item = self.client.post("/item", json={"name": "Load item", "price": 10})
        item.raise_for_status()
        item_id = item.json()["id"]
        cart = self.client.post("/cart")
        cart.raise_for_status()
        cart_id = cart.json()["id"]
        deadline = time.monotonic() + duration
        cycles = 0
        while time.monotonic() < deadline:
            for response in (
                self.client.get("/item"),
                self.client.get("/cart", params={"limit": 10}),
                self.client.get(f"/item/{item_id}"),
                self.client.post(f"/cart/{cart_id}/add/{item_id}"),
                self.client.get(f"/cart/{cart_id}"),
                self.client.patch(f"/item/{item_id}", json={"price": 10 + cycles % 2}),
            ):
                response.raise_for_status()
            missing = self.client.get("/item/0")
            if missing.status_code != 404:
                raise RuntimeError(f"Expected 404, received {missing.status_code}")
            deleted = self.client.delete(f"/item/{item_id}")
            deleted.raise_for_status()
            unavailable_cart = self.client.get(f"/cart/{cart_id}")
            unavailable_cart.raise_for_status()
            if unavailable_cart.json()["price"] != 0:
                raise RuntimeError("Deleted item still contributes to cart value")
            unavailable_add = self.client.post(f"/cart/{cart_id}/add/{item_id}")
            if unavailable_add.status_code != 404:
                raise RuntimeError(
                    f"Expected 404, received {unavailable_add.status_code}"
                )
            restored = self.client.put(
                f"/item/{item_id}", json={"name": "Load item", "price": 10}
            )
            restored.raise_for_status()
            cycles += 1
            time.sleep(interval)
        return cycles


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration", type=float, default=120)
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=5) as client:
        print(f"Completed {ShopLoad(client).run(args.duration, args.interval)} cycles")
