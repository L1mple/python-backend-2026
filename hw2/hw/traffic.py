import json
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "http://127.0.0.1:8082"
NAMES = (
    "milk",
    "bread",
    "cheese",
    "apple",
    "tea",
    "coffee",
    "rice",
    "pasta",
    "soap",
    "water",
)

items = []
carts = []
lock = threading.Lock()
stats = {}


def call(method, path, body=None, query=None):
    url = BASE + path
    if query:
        pairs = {key: value for key, value in query.items() if value is not None}
        if pairs:
            url += "?" + urllib.parse.urlencode(pairs)
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read()
        status = error.code
    with lock:
        stats[status] = stats.get(status, 0) + 1
    return status, raw


def item_body():
    return {
        "name": "%s-%s" % (random.choice(NAMES), random.randint(1, 9999)),
        "price": round(random.uniform(1, 500), 2),
    }


def remember(pool, value):
    with lock:
        pool.append(value)


def forget(pool, value):
    with lock:
        if value in pool:
            pool.remove(value)


def pick(pool, hit_rate=0.75):
    with lock:
        if pool and random.random() < hit_rate:
            return random.choice(pool)
    return random.randint(10000, 99999)


def create_item():
    status, raw = call("POST", "/item", item_body())
    if status == 201:
        remember(items, json.loads(raw)["id"])


def create_cart():
    status, raw = call("POST", "/cart")
    if status == 201:
        remember(carts, json.loads(raw)["id"])


def hit():
    kind = random.randrange(10)
    if kind == 0 or not items:
        create_item()
        return
    if kind == 1 or not carts:
        create_cart()
        return
    if kind == 2:
        call("GET", "/item/%s" % pick(items))
        return
    if kind == 3:
        call(
            "GET",
            "/item",
            query={
                "offset": random.choice((0, 0, 1, 5)),
                "limit": random.choice((5, 10, 20)),
                "min_price": random.choice((None, 1, 10, 50)),
                "max_price": random.choice((None, 100, 300, 1000)),
                "show_deleted": random.choice(("false", "true")),
            },
        )
        return
    if kind == 4:
        call("PUT", "/item/%s" % pick(items), item_body())
        return
    if kind == 5:
        body = {}
        if random.random() < 0.7:
            body["name"] = random.choice(NAMES)
        if random.random() < 0.7:
            body["price"] = round(random.uniform(1, 200), 2)
        call("PATCH", "/item/%s" % pick(items), body)
        return
    if kind == 6:
        item_id = pick(items, 0.6)
        call("DELETE", "/item/%s" % item_id)
        forget(items, item_id)
        return
    if kind == 7:
        call("GET", "/cart/%s" % pick(carts))
        return
    if kind == 8:
        call(
            "GET",
            "/cart",
            query={
                "offset": 0,
                "limit": random.choice((5, 10, 20)),
                "min_price": random.choice((None, 0, 10)),
                "max_price": random.choice((None, 100, 1000)),
                "min_quantity": random.choice((None, 0, 1)),
                "max_quantity": random.choice((None, 5, 20)),
            },
        )
        return
    call("POST", "/cart/%s/add/%s" % (pick(carts), pick(items)))


def wave(seconds, workers, pause):
    deadline = time.time() + seconds
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while time.time() < deadline:
            futures = [pool.submit(hit) for _ in range(workers)]
            for future in as_completed(futures):
                future.result()
            time.sleep(pause)


def main():
    for _ in range(8):
        create_item()
    for _ in range(4):
        create_cart()
    wave(20, 2, 0.3)
    wave(25, 12, 0.05)
    wave(15, 1, 0.5)
    wave(30, 16, 0.02)
    wave(20, 4, 0.15)
    print(dict(sorted(stats.items())))


if __name__ == "__main__":
    main()
