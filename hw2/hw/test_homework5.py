from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from shop_api.main import app

client = TestClient(app)

# такого id в базе точно нет
MISSING_ID = 10**9


@pytest.fixture()
def item_id() -> int:
    return client.post("/item", json={"name": "Чай", "price": 120.0}).json()["id"]


@pytest.fixture()
def cart_id() -> int:
    return client.post("/cart").json()["id"]


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("get", None),
        ("put", {"name": "Кофе", "price": 300.0}),
        ("patch", {"price": 300.0}),
        ("delete", None),
    ],
)
def test_missing_item(method: str, body: dict | None) -> None:
    response = client.request(method, f"/item/{MISSING_ID}", json=body)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_missing_cart() -> None:
    response = client.get(f"/cart/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_to_missing_cart(item_id: int) -> None:
    response = client.post(f"/cart/{MISSING_ID}/add/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item(cart_id: int) -> None:
    response = client.post(f"/cart/{cart_id}/add/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_deleted_item(cart_id: int, item_id: int) -> None:
    client.delete(f"/item/{item_id}")

    response = client.post(f"/cart/{cart_id}/add/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_same_item_twice(cart_id: int, item_id: int) -> None:
    client.post(f"/cart/{cart_id}/add/{item_id}")
    response = client.post(f"/cart/{cart_id}/add/{item_id}")

    assert response.status_code == HTTPStatus.OK
    # вторая строка не появляется, растёт количество
    assert response.json()["items"] == [
        {"id": item_id, "name": "Чай", "quantity": 2, "available": True}
    ]
    assert response.json()["price"] == pytest.approx(240.0)


def test_deleted_item_stays_in_cart(cart_id: int, item_id: int) -> None:
    client.post(f"/cart/{cart_id}/add/{item_id}")
    client.delete(f"/item/{item_id}")

    cart = client.get(f"/cart/{cart_id}").json()

    # товар остаётся в корзине, но помечен недоступным и в сумму не входит
    assert cart["items"][0]["available"] is False
    assert cart["price"] == 0.0
