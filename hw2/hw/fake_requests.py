from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from faker import Faker

faker = Faker()

IdempotencyTries = 3

def url(suffix : str):
    return "http://localhost:8080/" + suffix

def create_cart():
    result = None
    for attempt in range(IdempotencyTries):
        try:
            attempt = requests.post(url("cart"), timeout=5)
        except requests.RequestException as exc:
            continue
        else:
            if attempt.ok:  # 2xx → success, stop retrying
                result = attempt.json()["id"]

    return result

def create_item():
    payload = {
        "name": faker.word(),
        "price": round(faker.pyfloat(min_value=1.0, max_value=1000.0), 2),
    }

    result = None
    for _ in range(IdempotencyTries):
        try:
            attempt = requests.post(url("item"), json=payload, timeout=5)
        except requests.RequestException:
            continue
        else:
            if attempt.ok:
                result = attempt.json()["id"]

    return result

def add_item_to_cart(cart_id: int, item_id: int):
    for _ in range(IdempotencyTries):
        try:
            attempt = requests.post(
                url(f"cart/{cart_id}/add/{item_id}"), timeout=5
            )
        except requests.RequestException:
            continue
        else:
            if attempt.ok:
                return


def create_items_loop(n: int = 50) -> None:
    for _ in range(n):
        create_item()


def create_carts_loop(n: int = 50) -> None:
    for _ in range(n):
        create_cart()


import random
def populate_carts_loop(n: int = 200) -> None:
    # Selecting all ids on random to get some errors
    for _ in range(n):
        cart_id = random.randint(0, 10000)
        for _ in range(random.randint(1, 5)):
            item_id = random.randint(0, 10000)
            add_item_to_cart(cart_id, item_id)


def get_cart_loop(n: int = 500) -> None:
    for _ in range(n):
        requests.get(url(f"cart/{faker.random_number(digits=2)}"))


with ThreadPoolExecutor() as executor:
    futures = {}

    for i in range(15):
        futures[executor.submit(create_items_loop)] = f"create-items-{i}"

    for i in range(15):
        futures[executor.submit(create_carts_loop)] = f"create-carts-{i}"

    for i in range(10):
        futures[executor.submit(populate_carts_loop)] = f"populate-carts-{i}"

    for i in range(10):
        futures[executor.submit(get_cart_loop)] = f"get-carts-{i}"

    for future in as_completed(futures):
        print(f"completed {futures[future]}")

