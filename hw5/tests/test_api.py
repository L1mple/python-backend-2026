from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from shop_api.main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("resource", ["item", "cart"])
def test_page_beyond_last_resource_is_empty(client, resource):
    response = client.get(f"/{resource}", params={"offset": 10**9, "limit": 1})
    assert response.status_code == 200
    assert response.json() == []


def test_missing_item_delete_and_patch_do_not_create_resource(client):
    path = "/item/1000000000000"
    assert client.delete(path).status_code == 404
    response = client.patch(path, json={"name": "Missing", "price": 1})
    assert response.status_code == 304
    assert response.content == b""
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("price", [-1, "NaN", "Infinity", "-Infinity", None])
def test_invalid_price_is_rejected_without_changing_item(client, price):
    original = client.post("/item", json={"name": uuid4().hex, "price": 10}).json()
    path = f"/item/{original['id']}"
    assert client.post("/item", json={"name": "Invalid", "price": price}).status_code == 422
    assert client.put(path, json={"name": "Invalid", "price": price}).status_code == 422
    assert client.patch(path, json={"price": price}).status_code == 422
    assert client.get(path).json() == original
