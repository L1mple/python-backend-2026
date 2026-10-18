from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from faker import Faker


BASE_URL = "http://localhost:8000"
REQUESTS_PER_WORKER = 500
WORKERS = 15
faker = Faker()


def create_items():
    for _ in range(REQUESTS_PER_WORKER):
        response = httpx.post(
            f"{BASE_URL}/item",
            json={"name": faker.word(), "price": faker.pyfloat(min_value=1, max_value=1000)},
        )
        print(response)


def get_items():
    for _ in range(REQUESTS_PER_WORKER):
        response = httpx.get(
            f"{BASE_URL}/item",
            params={"limit": 10, "offset": faker.random_number(digits=2)},
        )
        print(response)


def create_carts():
    for _ in range(REQUESTS_PER_WORKER):
        response = httpx.post(f"{BASE_URL}/cart")
        print(response)


def get_carts():
    for _ in range(REQUESTS_PER_WORKER):
        response = httpx.get(
            f"{BASE_URL}/cart",
            params={"limit": 10, "offset": faker.random_number(digits=2)},
        )
        print(response)


with ThreadPoolExecutor() as executor:
    futures = {}

    for i in range(WORKERS):
        futures[executor.submit(create_items)] = f"create-items-{i}"
        futures[executor.submit(get_items)] = f"get-items-{i}"
        futures[executor.submit(create_carts)] = f"create-carts-{i}"
        futures[executor.submit(get_carts)] = f"get-carts-{i}"

    for future in as_completed(futures):
        future.result()
        print(f"completed {futures[future]}")
