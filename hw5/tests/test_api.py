from http import HTTPStatus
from itertools import count
from typing import Any

import pytest
from fastapi.testclient import TestClient

MISSING_ID = 10**9
_price_steps = count()


def unique_price() -> float:
    # Цены остальных тестов не превышают 500. Каждая следующая цена в 4 раза больше
    # предыдущей, поэтому диапазоны [p, 3p] разных тестов не пересекаются,
    # а x.5 точно представимо во float.
    return 10**6 * 4 ** next(_price_steps) + 0.5


def create_item(client: TestClient, price: float, name: str = 'item') -> dict[str, Any]:
    response = client.post('/item', json={'name': name, 'price': price})
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


def create_cart(client: TestClient) -> int:
    response = client.post('/cart')
    assert response.status_code == HTTPStatus.CREATED
    cart_id = response.json()['id']
    assert response.headers['location'] == f'/cart/{cart_id}'
    return cart_id


class TestItemNotFound:
    def test_get_missing(self, client: TestClient) -> None:
        response = client.get(f'/item/{MISSING_ID}')

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.text == 'Object not Found'

    def test_put_missing(self, client: TestClient) -> None:
        response = client.put(f'/item/{MISSING_ID}', json={'name': 'x', 'price': 1.0})

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_put_deleted(self, client: TestClient) -> None:
        item = create_item(client, 10.0)
        client.delete(f'/item/{item["id"]}')

        response = client.put(f'/item/{item["id"]}', json={'name': 'x', 'price': 1.0})

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_patch_missing(self, client: TestClient) -> None:
        response = client.patch(f'/item/{MISSING_ID}', json={'price': 1.0})

        assert response.status_code == HTTPStatus.NOT_MODIFIED

    def test_delete_missing(self, client: TestClient) -> None:
        response = client.delete(f'/item/{MISSING_ID}')

        assert response.status_code == HTTPStatus.OK


class TestItemUpdate:
    def test_put_replaces_item(self, client: TestClient) -> None:
        item = create_item(client, 10.0, name='old')

        response = client.put(f'/item/{item["id"]}', json={'name': 'new', 'price': 20.0})

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {'id': item['id'], 'name': 'new', 'price': 20.0, 'deleted': False}
        assert client.get(f'/item/{item["id"]}').json() == response.json()

    def test_patch_changes_only_given_fields(self, client: TestClient) -> None:
        item = create_item(client, 10.0, name='old')

        response = client.patch(f'/item/{item["id"]}', json={'name': 'new'})

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {**item, 'name': 'new'}

    def test_post_validates_body(self, client: TestClient) -> None:
        response = client.post('/item', json={'name': 'no price'})

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


class TestItemList:
    def test_price_filter_is_inclusive(self, client: TestClient) -> None:
        price = unique_price()
        item = create_item(client, price)

        response = client.get('/item', params={'min_price': price, 'max_price': price})

        assert response.status_code == HTTPStatus.OK
        assert response.json() == [item]

    def test_deleted_hidden_by_default(self, client: TestClient) -> None:
        price = unique_price()
        alive = create_item(client, price)
        deleted = create_item(client, price)
        client.delete(f'/item/{deleted["id"]}')
        params = {'min_price': price, 'max_price': price}

        default = client.get('/item', params=params).json()
        with_deleted = client.get('/item', params={**params, 'show_deleted': True}).json()

        assert default == [alive]
        assert with_deleted == [alive, {**deleted, 'deleted': True}]

    def test_pagination(self, client: TestClient) -> None:
        price = unique_price()
        items = [create_item(client, price, name=f'item {i}') for i in range(5)]
        params = {'min_price': price, 'max_price': price}

        page = client.get('/item', params={**params, 'offset': 1, 'limit': 2}).json()
        tail = client.get('/item', params={**params, 'offset': 4, 'limit': 10}).json()
        beyond = client.get('/item', params={**params, 'offset': 5}).json()

        assert page == items[1:3]
        assert tail == items[4:]
        assert beyond == []


class TestCart:
    def test_get_missing(self, client: TestClient) -> None:
        response = client.get(f'/cart/{MISSING_ID}')

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.text == 'Object not Found'

    def test_add_to_missing_cart(self, client: TestClient) -> None:
        item = create_item(client, 10.0)

        response = client.post(f'/cart/{MISSING_ID}/add/{item["id"]}')

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_add_missing_item(self, client: TestClient) -> None:
        cart_id = create_cart(client)

        response = client.post(f'/cart/{cart_id}/add/{MISSING_ID}')

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_add_deleted_item(self, client: TestClient) -> None:
        cart_id = create_cart(client)
        item = create_item(client, 10.0)
        client.delete(f'/item/{item["id"]}')

        response = client.post(f'/cart/{cart_id}/add/{item["id"]}')

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_add_same_item_increments_quantity(self, client: TestClient) -> None:
        cart_id = create_cart(client)
        first = create_item(client, 10.5, name='first')
        second = create_item(client, 2.25, name='second')

        client.post(f'/cart/{cart_id}/add/{first["id"]}')
        client.post(f'/cart/{cart_id}/add/{second["id"]}')
        response = client.post(f'/cart/{cart_id}/add/{first["id"]}')

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {
            'id': cart_id,
            'items': [
                {'id': first['id'], 'name': 'first', 'quantity': 2, 'available': True},
                {'id': second['id'], 'name': 'second', 'quantity': 1, 'available': True},
            ],
            'price': 23.25,
        }

    def test_deleted_item_becomes_unavailable(self, client: TestClient) -> None:
        cart_id = create_cart(client)
        item = create_item(client, 10.0)
        client.post(f'/cart/{cart_id}/add/{item["id"]}')

        client.delete(f'/item/{item["id"]}')
        cart = client.get(f'/cart/{cart_id}').json()

        assert cart['items'] == [{'id': item['id'], 'name': 'item', 'quantity': 1, 'available': False}]

    def test_item_changes_are_reflected(self, client: TestClient) -> None:
        cart_id = create_cart(client)
        item = create_item(client, 10.0)
        client.post(f'/cart/{cart_id}/add/{item["id"]}')

        client.put(f'/item/{item["id"]}', json={'name': 'renamed', 'price': 30.0})
        cart = client.get(f'/cart/{cart_id}').json()

        assert cart['items'][0]['name'] == 'renamed'
        assert cart['price'] == 30.0


class TestCartList:
    @pytest.fixture()
    def carts(self, client: TestClient) -> tuple[float, list[int]]:
        """Две корзины с уникальной ценой товара: в первой 1 штука, во второй 3."""
        price = unique_price()
        item = create_item(client, price)
        one, three = create_cart(client), create_cart(client)
        client.post(f'/cart/{one}/add/{item["id"]}')
        for _ in range(3):
            client.post(f'/cart/{three}/add/{item["id"]}')
        return price, [one, three]

    @staticmethod
    def ids(response) -> list[int]:
        assert response.status_code == HTTPStatus.OK
        return [cart['id'] for cart in response.json()]

    def test_price_filters(self, client: TestClient, carts: tuple[float, list[int]]) -> None:
        price, (one, three) = carts

        assert self.ids(client.get('/cart', params={'min_price': price, 'max_price': price})) == [one]
        assert self.ids(client.get('/cart', params={'min_price': price * 3, 'max_price': price * 3})) == [three]
        assert self.ids(client.get('/cart', params={'min_price': price, 'max_price': price * 3})) == [one, three]

    def test_quantity_filters(self, client: TestClient, carts: tuple[float, list[int]]) -> None:
        price, (one, three) = carts
        params = {'min_price': price, 'max_price': price * 3}

        assert self.ids(client.get('/cart', params={**params, 'min_quantity': 2})) == [three]
        assert self.ids(client.get('/cart', params={**params, 'max_quantity': 2})) == [one]
        assert self.ids(client.get('/cart', params={**params, 'min_quantity': 4})) == []

    def test_pagination(self, client: TestClient, carts: tuple[float, list[int]]) -> None:
        price, (one, three) = carts
        params = {'min_price': price, 'max_price': price * 3}

        assert self.ids(client.get('/cart', params={**params, 'limit': 1})) == [one]
        assert self.ids(client.get('/cart', params={**params, 'offset': 1})) == [three]

    def test_empty_cart_matches_zero_filters(self, client: TestClient) -> None:
        cart_id = create_cart(client)
        params = {'max_price': 0, 'max_quantity': 0, 'limit': 10**4}

        assert cart_id in self.ids(client.get('/cart', params=params))
