from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from faker import Faker

faker = Faker()
BASE = "http://localhost:8079"


def create_items():
    for _ in range(200):
        requests.post(f"{BASE}/item", json={
            "name": faker.word(),
            "price": faker.pyfloat(min_value=1, max_value=1000),
        })


def get_items():
    for _ in range(200):
        requests.get(f"{BASE}/item", params={"limit": 10})


def create_carts():
    for _ in range(200):
        requests.post(f"{BASE}/cart")


with ThreadPoolExecutor() as executor:
    futures = []
    for _ in range(5):
        futures.append(executor.submit(create_items))
        futures.append(executor.submit(get_items))
        futures.append(executor.submit(create_carts))

    for future in as_completed(futures):
        print("done")