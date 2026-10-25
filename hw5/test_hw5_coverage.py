"""Additional behavioral tests for the original in-memory Shop API (HW5)."""
import pytest
from fastapi.testclient import TestClient
from shop_api.main import app, items, carts

client = TestClient(app)

@pytest.fixture(autouse=True)
def isolated_storage():
    # Extra tests run independently from the original HW2 test module.
    items.clear()
    carts.clear()
    yield
    items.clear()
    carts.clear()


def test_missing_item_and_cart_are_404():
    assert client.get('/item/999').status_code == 404
    assert client.get('/cart/999').status_code == 404
    assert client.put('/item/999', json={'name':'other','price':10}).status_code == 404
    assert client.post('/cart/999/add/999').status_code == 404


def test_deleted_items_filtered_and_excluded_from_cart_total():
    first = client.post('/item', json={'name':'first', 'price':30}).json()['id']
    second = client.post('/item', json={'name':'second', 'price':40}).json()['id']
    cart = client.post('/cart').json()['id']
    assert client.post(f'/cart/{cart}/add/{first}').status_code == 200
    assert client.post(f'/cart/{cart}/add/{second}').status_code == 200
    assert client.delete(f'/item/{first}').status_code == 200
    assert client.get('/item').json() == [{'id':second,'name':'second','price':40.0,'deleted':False}]
    assert len(client.get('/item?show_deleted=true').json()) == 2
    response = client.get(f'/cart/{cart}').json()
    assert response['price'] == 40
    assert {x['id']:x['available'] for x in response['items']} == {first:False,second:True}


def test_minimum_price_filter_excludes_cheaper_products():
    client.post('/item', json={'name':'cheap','price':5})
    expensive = client.post('/item', json={'name':'expensive','price':100}).json()
    assert client.get('/item?min_price=50').json() == [expensive]


@pytest.mark.parametrize('field', ['name','price'])
def test_patch_rejects_explicit_null(field):
    item = client.post('/item', json={'name':'test','price':20}).json()['id']
    response = client.patch(f'/item/{item}',json={field:None})
    assert response.status_code == 422
    assert client.get(f'/item/{item}').json()['price'] == 20


def test_add_same_product_twice_to_cart():
    item = client.post('/item',json={'name':'test','price':7}).json()['id']
    cart = client.post('/cart').json()['id']
    client.post(f'/cart/{cart}/add/{item}')
    result = client.post(f'/cart/{cart}/add/{item}')
    assert result.status_code == 200
    assert result.json()['items'][0]['quantity'] == 2
    assert result.json()['price'] == 14
