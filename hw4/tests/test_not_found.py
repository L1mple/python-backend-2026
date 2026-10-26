from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from shop_api.main import app

MISSING_ID = 10**9


@pytest.fixture(scope="module")
def client():
    # context manager runs lifespan, so init_db() is covered too
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def item_id(client: TestClient) -> int:
    return client.post("/item", json={"name": "товар", "price": 10.0}).json()["id"]


@pytest.fixture()
def cart_id(client: TestClient) -> int:
    return client.post("/cart").json()["id"]


def test_get_missing_cart(client: TestClient) -> None:
    response = client.get(f"/cart/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_missing_cart(client: TestClient, item_id: int) -> None:
    response = client.post(f"/cart/{MISSING_ID}/add/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item_to_cart(client: TestClient, cart_id: int) -> None:
    response = client.post(f"/cart/{cart_id}/add/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert client.get(f"/cart/{cart_id}").json()["items"] == []


def test_add_same_item_twice(client: TestClient, cart_id: int, item_id: int) -> None:
    client.post(f"/cart/{cart_id}/add/{item_id}")
    response = client.post(f"/cart/{cart_id}/add/{item_id}")

    assert response.status_code == HTTPStatus.OK
    cart = response.json()
    assert cart["items"] == [
        {"id": item_id, "name": "товар", "quantity": 2, "available": True}
    ]
    assert cart["price"] == pytest.approx(20.0)


def test_put_missing_item(client: TestClient) -> None:
    response = client.put(f"/item/{MISSING_ID}", json={"name": "x", "price": 1.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_missing_item(client: TestClient) -> None:
    response = client.patch(f"/item/{MISSING_ID}", json={"price": 1.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_missing_item(client: TestClient) -> None:
    response = client.delete(f"/item/{MISSING_ID}")
    assert response.status_code == HTTPStatus.OK
