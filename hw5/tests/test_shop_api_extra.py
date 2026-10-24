"""Дополнительные тесты ДЗ2 для покрытия граничных ситуаций API."""

from fastapi.testclient import TestClient

from shop_api.main import CartEntity, CartResponse, app

client = TestClient(app)


def test_get_nonexistent_cart_returns_404():
    response = client.get('/cart/999999999')
    assert response.status_code == 404


def test_add_item_to_nonexistent_cart_returns_404():
    response = client.post('/cart/999999999/add/1')
    assert response.status_code == 404


def test_add_nonexistent_item_to_existing_cart_returns_404():
    cart_id = client.post('/cart').json()['id']
    response = client.post(f'/cart/{cart_id}/add/999999999')
    assert response.status_code == 404


def test_cart_ignores_missing_referenced_item():
    # Проверяем защиту от устаревшей ссылки на несуществующий товар.
    cart = CartEntity(id=1, items={-999999: 3})
    result = CartResponse.from_entity(cart)
    assert result.items == []
    assert result.price == 0


def test_deleted_item_hidden_from_default_list():
    item = client.post('/item', json={'name': 'temporary hidden item', 'price': 42}).json()
    assert client.delete(f"/item/{item['id']}").status_code == 200

    default_items = client.get('/item', params={'limit': 100000}).json()
    assert item['id'] not in {row['id'] for row in default_items}

    deleted_items = client.get('/item', params={'show_deleted': True, 'limit': 100000}).json()
    assert any(row['id'] == item['id'] and row['deleted'] for row in deleted_items)


def test_item_listing_filters_minimum_and_maximum_price():
    item = client.post('/item', json={'name': 'price-filter-item', 'price': 57.5}).json()
    all_ids = lambda params: {
        row['id'] for row in client.get('/item', params={'limit': 100000, **params}).json()
    }
    assert item['id'] not in all_ids({'min_price': 60})
    assert item['id'] not in all_ids({'max_price': 50})
    assert item['id'] in all_ids({'min_price': 57.5, 'max_price': 57.5})


def test_put_nonexistent_item_returns_304():
    # Такое поведение определено существующей реализацией ДЗ2.
    response = client.put('/item/999999999', json={'name': 'missing', 'price': 1.0})
    assert response.status_code == 304


def test_add_same_item_twice_updates_quantity():
    item = client.post('/item', json={'name': 'repeatable item', 'price': 25}).json()
    cart_id = client.post('/cart').json()['id']
    for _ in range(2):
        response = client.post(f"/cart/{cart_id}/add/{item['id']}")
        assert response.status_code == 200
    cart = client.get(f'/cart/{cart_id}').json()
    assert cart['items'][0]['quantity'] == 2
    assert cart['price'] == 50
