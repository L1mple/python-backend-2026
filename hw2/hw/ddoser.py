from concurrent.futures import ThreadPoolExecutor

import requests
from faker import Faker

faker = Faker()
BASE = 'http://localhost:8080'


def create_items():
    for _ in range(100):
        response = requests.post(
            f'{BASE}/item',
            json={
                'name': faker.word(),
                'price': faker.pyfloat(positive=True, min_value=1, max_value=100),
            },
        )
        print(response)


def create_carts_and_add():
    for _ in range(100):
        cart = requests.post(f'{BASE}/cart')
        print(cart)
        cart_id = cart.json().get('id')
        if cart_id is None:
            continue
        item_id = faker.random_int(min=1, max=50)
        response = requests.post(f'{BASE}/cart/{cart_id}/add/{item_id}')
        print(response)


def get_lists():
    for _ in range(100):
        print(requests.get(f'{BASE}/item'))
        print(requests.get(f'{BASE}/cart'))


with ThreadPoolExecutor() as executor:
    for i in range(10):
        executor.submit(create_items)
    for i in range(10):
        executor.submit(create_carts_and_add)
    for i in range(10):
        executor.submit(get_lists)
