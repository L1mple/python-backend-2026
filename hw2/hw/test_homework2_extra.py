from __future__ import annotations

from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from shop_api.main import app

client = TestClient(app)

NONEXISTENT_ID = 2**31 - 1


def unique_name(prefix: str = "item") -> str:
    return f"{prefix} {uuid4().hex}"


def create_item(name: str | None = None, price: float = 100.0) -> dict[str, Any]:
    response = client.post(
        "/item",
        json={"name": name or unique_name(), "price": price},
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


def create_cart() -> int:
    response = client.post("/cart")
    assert response.status_code == HTTPStatus.CREATED
    return response.json()["id"]


def get_cart(cart_id: int) -> dict[str, Any]:
    response = client.get(f"/cart/{cart_id}")
    assert response.status_code == HTTPStatus.OK
    return response.json()


def add_item(cart_id: int, item_id: int) -> dict[str, Any]:
    response = client.post(f"/cart/{cart_id}/add/{item_id}")
    assert response.status_code == HTTPStatus.OK
    return response.json()


def list_items(**params: Any) -> list[dict[str, Any]]:
    response = client.get("/item", params=params)
    assert response.status_code == HTTPStatus.OK
    return response.json()


def list_carts(**params: Any) -> list[dict[str, Any]]:
    response = client.get("/cart", params=params)
    assert response.status_code == HTTPStatus.OK
    return response.json()


def test_item_creation_and_get() -> None:
    item = create_item(name=unique_name("zero price"), price=0.0)

    assert set(item) == {"id", "name", "price", "deleted"}
    assert isinstance(item["id"], int)
    assert item["price"] == 0.0
    assert item["deleted"] is False
    assert client.get(f"/item/{item['id']}").json() == item

    for payload in (
        {},
        {"name": "only name"},
        {"price": 10.0},
        {"name": "", "price": 10.0},
        {"name": "negative price", "price": -0.01},
    ):
        assert client.post("/item", json=payload).status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    assert client.get(f"/item/{NONEXISTENT_ID}").status_code == HTTPStatus.NOT_FOUND


def test_item_list_filters_and_price_boundaries() -> None:
    low_price = 9_100_001.25
    middle_price = 9_100_002.5
    high_price = 9_100_003.75

    low_item = create_item(price=low_price)
    middle_item = create_item(price=middle_price)
    high_item = create_item(price=high_price)

    assert client.delete(f"/item/{middle_item['id']}").status_code == HTTPStatus.OK

    filtered = list_items(min_price=low_price, max_price=high_price, limit=100_000)
    filtered_ids = {item["id"] for item in filtered}

    assert low_item["id"] in filtered_ids
    assert high_item["id"] in filtered_ids
    assert middle_item["id"] not in filtered_ids
    assert all(low_price <= item["price"] <= high_price for item in filtered)
    assert list_items(min_price=middle_price, max_price=middle_price) == []

    visible = list_items(
        min_price=middle_price,
        max_price=middle_price,
        show_deleted=True,
    )
    assert [item["id"] for item in visible] == [middle_item["id"]]
    assert visible[0]["deleted"] is True

    assert low_item["id"] in {
        item["id"] for item in list_items(min_price=low_price, limit=100_000)
    }
    assert high_item["id"] in {
        item["id"] for item in list_items(max_price=high_price, limit=100_000)
    }


def test_item_list_pagination_and_query_validation() -> None:
    all_items = list_items(limit=100_000)

    assert len(list_items()) == min(10, len(all_items))
    assert [item["id"] for item in list_items(offset=1, limit=3)] == [
        item["id"] for item in all_items[1:4]
    ]
    assert list_items(offset=len(all_items) + 100) == []

    for params in (
        {"offset": -1},
        {"limit": 0},
        {"limit": -1},
        {"min_price": -1.0},
        {"max_price": -1.0},
        {"offset": "not-a-number"},
        {"limit": "not-a-number"},
        {"show_deleted": "not-a-bool"},
    ):
        assert client.get("/item", params=params).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_item_put_replaces_and_validates() -> None:
    item = create_item(price=9_200_001.0)
    new_name = unique_name("replaced")
    new_price = 9_200_002.0

    response = client.put(
        f"/item/{item['id']}",
        json={"name": new_name, "price": new_price},
    )

    assert response.status_code == HTTPStatus.OK
    replaced = response.json()
    assert replaced == {
        "id": item["id"],
        "name": new_name,
        "price": new_price,
        "deleted": False,
    }
    assert client.get(f"/item/{item['id']}").json() == replaced

    body = {"name": unique_name(), "price": 1.0}
    assert client.put(f"/item/{NONEXISTENT_ID}", json=body).status_code == HTTPStatus.NOT_FOUND
    assert client.get(f"/item/{NONEXISTENT_ID}").status_code == HTTPStatus.NOT_FOUND

    deleted_item = create_item()
    client.delete(f"/item/{deleted_item['id']}")
    assert client.put(f"/item/{deleted_item['id']}", json=body).status_code == HTTPStatus.NOT_FOUND

    for payload in (
        {},
        {"name": "only name"},
        {"price": 1.0},
        {"name": "", "price": 1.0},
        {"name": "negative price", "price": -1.0},
    ):
        assert client.put(f"/item/{item['id']}", json=payload).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_item_patch_updates_only_given_fields_and_validates() -> None:
    item = create_item(price=9_300_001.0)
    new_name = unique_name("patched")

    response = client.patch(f"/item/{item['id']}", json={"name": new_name})
    assert response.status_code == HTTPStatus.OK
    patched = response.json()
    assert patched == {
        "id": item["id"],
        "name": new_name,
        "price": item["price"],
        "deleted": False,
    }
    assert client.get(f"/item/{item['id']}").json() == patched

    new_price = 9_300_002.0
    response = client.patch(f"/item/{item['id']}", json={"price": new_price})
    assert response.status_code == HTTPStatus.OK
    patched = response.json()
    assert patched == {
        "id": item["id"],
        "name": new_name,
        "price": new_price,
        "deleted": False,
    }
    assert client.get(f"/item/{item['id']}").json() == patched

    assert client.patch(f"/item/{item['id']}", json={}).status_code == HTTPStatus.OK
    assert client.patch(f"/item/{item['id']}", json={}).json() == patched
    assert client.patch(f"/item/{NONEXISTENT_ID}", json={"price": 1.0}).status_code == HTTPStatus.NOT_FOUND

    deleted_item = create_item()
    client.delete(f"/item/{deleted_item['id']}")
    assert client.patch(f"/item/{deleted_item['id']}", json={"price": 1.0}).status_code == HTTPStatus.NOT_MODIFIED

    for payload in (
        {"unknown_field": "value"},
        {"deleted": True},
        {"name": "", "price": 1.0},
        {"price": -1.0},
    ):
        assert client.patch(f"/item/{item['id']}", json=payload).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_delete_item_hides_from_lists_and_is_idempotent() -> None:
    item = create_item(price=9_400_001.0)

    assert client.delete(f"/item/{item['id']}").status_code == HTTPStatus.OK
    assert client.delete(f"/item/{item['id']}").status_code == HTTPStatus.OK
    assert client.get(f"/item/{item['id']}").status_code == HTTPStatus.NOT_FOUND
    assert item["id"] not in {i["id"] for i in list_items(limit=100_000)}

    visible = {i["id"]: i for i in list_items(show_deleted=True, limit=100_000)}
    assert visible[item["id"]]["deleted"] is True
    assert client.delete(f"/item/{NONEXISTENT_ID}").status_code == HTTPStatus.NOT_FOUND


def test_cart_creation_and_adding_items() -> None:
    response = client.post("/cart")

    assert response.status_code == HTTPStatus.CREATED
    cart_id = response.json()["id"]
    assert response.headers["location"] == f"/cart/{cart_id}"
    assert get_cart(cart_id) == {"id": cart_id, "items": [], "price": 0.0}
    assert client.get(f"/cart/{NONEXISTENT_ID}").status_code == HTTPStatus.NOT_FOUND

    first_item = create_item(price=9_500_001.5)
    first_cart = add_item(cart_id, first_item["id"])
    assert first_cart["items"] == [
        {
            "id": first_item["id"],
            "name": first_item["name"],
            "quantity": 1,
            "available": True,
        }
    ]
    assert first_cart["price"] == pytest.approx(first_item["price"])

    second_cart = add_item(cart_id, first_item["id"])
    assert len(second_cart["items"]) == 1
    assert second_cart["items"][0]["quantity"] == 2
    assert second_cart["price"] == pytest.approx(2 * first_item["price"])

    second_item = create_item(price=9_500_003.5)
    third_cart = add_item(cart_id, second_item["id"])
    quantities = {item["id"]: item["quantity"] for item in third_cart["items"]}
    assert quantities == {first_item["id"]: 2, second_item["id"]: 1}
    assert third_cart["price"] == pytest.approx(
        2 * first_item["price"] + second_item["price"]
    )
    assert get_cart(cart_id) == third_cart

    assert client.post(f"/cart/{NONEXISTENT_ID}/add/{first_item['id']}").status_code == HTTPStatus.NOT_FOUND
    assert client.post(f"/cart/{cart_id}/add/{NONEXISTENT_ID}").status_code == HTTPStatus.NOT_FOUND

    deleted_item = create_item()
    client.delete(f"/item/{deleted_item['id']}")
    empty_cart_id = create_cart()
    assert client.post(f"/cart/{empty_cart_id}/add/{deleted_item['id']}").status_code == HTTPStatus.NOT_FOUND
    assert get_cart(empty_cart_id)["items"] == []


def test_cart_list_price_and_quantity_filters() -> None:
    first_price = 9_600_001.25
    second_price = 9_600_002.5

    first_cart_id = create_cart()
    first_item = create_item(price=first_price)
    add_item(first_cart_id, first_item["id"])

    second_cart_id = create_cart()
    second_item = create_item(price=second_price)
    add_item(second_cart_id, second_item["id"])

    price_page = list_carts(
        min_price=first_price,
        max_price=first_price,
        limit=100_000,
    )
    price_page_ids = {cart["id"] for cart in price_page}
    assert first_cart_id in price_page_ids
    assert second_cart_id not in price_page_ids
    assert all(cart["price"] == pytest.approx(first_price) for cart in price_page)

    empty_cart_id = create_cart()
    zero_price_page = list_carts(max_price=0.0, limit=100_000)
    assert empty_cart_id in {cart["id"] for cart in zero_price_page}
    assert all(cart["price"] == 0.0 for cart in zero_price_page)

    quantity_cart_id = create_cart()
    quantity_item = create_item()
    for _ in range(3):
        add_item(quantity_cart_id, quantity_item["id"])

    quantity_page = list_carts(min_quantity=3, max_quantity=3, limit=100_000)
    assert quantity_cart_id in {cart["id"] for cart in quantity_page}
    assert all(
        sum(item["quantity"] for item in cart["items"]) == 3
        for cart in quantity_page
    )

    empty_quantity_page = list_carts(max_quantity=0, limit=100_000)
    assert empty_cart_id in {cart["id"] for cart in empty_quantity_page}
    assert all(
        sum(item["quantity"] for item in cart["items"]) == 0
        for cart in empty_quantity_page
    )


def test_cart_list_pagination_and_query_validation() -> None:
    all_carts = list_carts(limit=100_000)

    assert len(list_carts()) == min(10, len(all_carts))
    assert [cart["id"] for cart in list_carts(offset=1, limit=2)] == [
        cart["id"] for cart in all_carts[1:3]
    ]
    assert list_carts(offset=len(all_carts) + 100) == []

    for params in (
        {"offset": -1},
        {"limit": 0},
        {"limit": -1},
        {"min_price": -1.0},
        {"max_price": -1.0},
        {"min_quantity": -1},
        {"max_quantity": -1},
    ):
        assert client.get("/cart", params=params).status_code == HTTPStatus.UNPROCESSABLE_ENTITY
