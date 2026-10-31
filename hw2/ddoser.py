from concurrent.futures import ThreadPoolExecutor, as_completed
import random

import requests
from faker import Faker

faker = Faker()
BASE = "http://localhost:8080"


def create_pokemons():
    for _ in range(200):
        requests.post(
            f"{BASE}/pokemon/",
            json={"name": faker.first_name(), "published": True},
        )


def get_pokemons():
    for _ in range(500):
        requests.get(f"{BASE}/pokemon/", params={"offset": 0, "limit": 10})


def get_one_pokemon():
    for _ in range(500):
        requests.get(f"{BASE}/pokemon/{random.randint(0, 100)}")


def patch_pokemon():
    for _ in range(200):
        requests.patch(
            f"{BASE}/pokemon/{random.randint(0, 100)}",
            json={"published": False},
        )


with ThreadPoolExecutor() as executor:
    futures = {}
    for i in range(4):
        futures[executor.submit(create_pokemons)] = f"create-{i}"
        futures[executor.submit(get_pokemons)] = f"list-{i}"
        futures[executor.submit(get_one_pokemon)] = f"get-one-{i}"
        futures[executor.submit(patch_pokemon)] = f"patch-{i}"

    for future in as_completed(futures):
        print(f"completed {futures[future]}")
