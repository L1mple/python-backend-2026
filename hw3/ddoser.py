from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from faker import Faker

faker = Faker()

BASE_URL = "http://127.0.0.1:8000"

TIMES = 50


def create_items():
    for _ in range(TIMES):
        requests.post(f"{BASE_URL}/item", json={
            "name": faker.name(),
            "price": faker.pyfloat(min_value=0.1, max_value=1000.0),
        })


def get_items():
    for _ in range(TIMES):
        requests.get(
            f"{BASE_URL}/item",
            params={"limit": 10, "offset": faker.random_int(min=0, max=25)},
        )


def create_carts():
    for _ in range(TIMES):
        requests.post(f"{BASE_URL}/cart")


def get_carts():
    for _ in range(TIMES):
        cart_id = faker.random_int(min=0, max=TIMES)
        requests.get(f"{BASE_URL}/cart/{cart_id}")


with ThreadPoolExecutor() as executor:
    while True:
        futures = [
            executor.submit(create_items),
            executor.submit(get_items),
            executor.submit(create_carts),
            executor.submit(get_carts),
        ]

        import time

        time.sleep(2)

        for future in as_completed(futures):
            print(f"completed")
