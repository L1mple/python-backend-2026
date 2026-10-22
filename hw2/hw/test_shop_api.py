import pytest
from fastapi.testclient import TestClient
from shop_api.main import app

client = TestClient(app)


@pytest.mark.parametrize(('method', 'path', 'body'), [
    ('get', '/cart/2147483647', None),
    ('get', '/item/2147483647', None),
    ('post', '/cart/2147483647/add/2147483647', None),
    ('put', '/item/2147483647', {'name': 'Missing', 'price': 1}),
    ('patch', '/item/2147483647', {'price': 1}),
    ('delete', '/item/2147483647', None),
])
def test_missing_resource(method, path, body):
    assert client.request(method, path, json=body).status_code == 404


def test_deleted_item_in_cart():
    item = client.post('/item', json={'name': 'Milk', 'price': 10}).json()
    cart = client.post('/cart').json()['id']
    path = f"/item/{item['id']}"
    assert client.post(f'/cart/{cart}/add/2147483647').status_code == 404

    for _ in range(2):
        assert client.post(f"/cart/{cart}/add/{item['id']}").status_code == 200

    assert client.get(f'/cart/{cart}').json()['price'] == 20
    assert client.patch(path, json={'price': None}).status_code == 422
    assert client.get(path).json() == item

    client.delete(path)

    assert client.put(path, json={'name': 'Other', 'price': 1}).status_code == 304
    assert client.post(f"/cart/{cart}/add/{item['id']}").status_code == 404

    result = client.get(f'/cart/{cart}').json()
    assert result['price'] == 0
    assert result['items'] == [{'id': item['id'], 'name': 'Milk', 'quantity': 2, 'available': False}]
