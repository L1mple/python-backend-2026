from http import HTTPStatus
from typing import Any

import pytest

from tests.conftest import client


def test_post_cart() -> None:
    response = client.post("/cart")

    assert response.status_code == HTTPStatus.CREATED
    assert "location" in response.headers
    assert "id" in response.json()


@pytest.mark.parametrize(
    ("cart", "not_empty"),
    [
        ("existing_empty_cart_id", False),
        ("existing_not_empty_cart_id", True),
    ],
)
def test_get_cart(request, cart: int, not_empty: bool) -> None:
    cart_id = request.getfixturevalue(cart)

    response = client.get(f"/cart/{cart_id}")

    assert response.status_code == HTTPStatus.OK
    response_json = response.json()

    len_items = len(response_json["items"])
    assert len_items > 0 if not_empty else len_items == 0

    if not_empty:
        price = 0
        for item in response_json["items"]:
            item_id = item["id"]
            price += client.get(f"/item/{item_id}").json()["price"] * item["quantity"]
        assert response_json["price"] == pytest.approx(price, 1e-8)
    else:
        assert response_json["price"] == 0.0


def test_get_cart_by_id_not_found() -> None:
    response = client.get("/cart/999999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("query", "status_code"),
    [
        ({}, HTTPStatus.OK),
        ({"offset": 1, "limit": 2}, HTTPStatus.OK),
        ({"min_price": 1000.0}, HTTPStatus.OK),
        ({"max_price": 20.0}, HTTPStatus.OK),
        ({"min_quantity": 1}, HTTPStatus.OK),
        ({"max_quantity": 0}, HTTPStatus.OK),
        ({"offset": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"limit": 0}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"limit": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"min_price": -1.0}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"max_price": -1.0}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"min_quantity": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"max_quantity": -1}, HTTPStatus.UNPROCESSABLE_ENTITY),
    ],
)
def test_get_cart_list(query: dict[str, Any], status_code: int) -> None:
    response = client.get("/cart", params=query)

    assert response.status_code == status_code

    if status_code == HTTPStatus.OK:
        data = response.json()
        assert isinstance(data, list)

        if "min_price" in query:
            assert all(item["price"] >= query["min_price"] for item in data)
        if "max_price" in query:
            assert all(item["price"] <= query["max_price"] for item in data)

        quantity = sum(item["quantity"] for cart in data for item in cart["items"])
        if "min_quantity" in query:
            assert quantity >= query["min_quantity"]
        if "max_quantity" in query:
            assert quantity <= query["max_quantity"]


def test_add_item_to_cart(existing_empty_cart_id: int, existing_item: dict[str, Any]) -> None:
    item_id = existing_item["id"]
    response = client.post(f"/cart/{existing_empty_cart_id}/add/{item_id}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == existing_empty_cart_id
    ids = [item["id"] for item in data["items"]]
    assert item_id in ids


def test_add_item_to_cart_twice_increments_quantity(
    existing_empty_cart_id: int,
    existing_item: dict[str, Any],
) -> None:
    item_id = existing_item["id"]
    client.post(f"/cart/{existing_empty_cart_id}/add/{item_id}")
    response = client.post(f"/cart/{existing_empty_cart_id}/add/{item_id}")

    assert response.status_code == HTTPStatus.OK
    positions = {item["id"]: item["quantity"] for item in response.json()["items"]}
    assert positions[item_id] == 2


def test_add_item_to_cart_cart_not_found(existing_item: dict[str, Any]) -> None:
    item_id = existing_item["id"]
    response = client.post(f"/cart/999999999/add/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_cart_item_not_found(existing_empty_cart_id: int) -> None:
    response = client.post(f"/cart/{existing_empty_cart_id}/add/999999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_cart_with_deleted_item_reports_unavailable(
    existing_empty_cart_id: int,
    existing_item: dict[str, Any],
) -> None:
    item_id = existing_item["id"]
    client.post(f"/cart/{existing_empty_cart_id}/add/{item_id}")
    client.delete(f"/item/{item_id}")

    response = client.get(f"/cart/{existing_empty_cart_id}")

    assert response.status_code == HTTPStatus.OK
    positions = {item["id"]: item for item in response.json()["items"]}
    assert item_id in positions
    assert positions[item_id]["available"] is False