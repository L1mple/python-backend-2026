from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import pytest
from faker import Faker
from fastapi.testclient import TestClient
from shop_api.main import Cart, CartItem, ListParams, apply_list_params

faker = Faker()

NOT_EXISTING_ID = 10**9


@dataclass
class Priced:
    price: float


@pytest.fixture()
def items_in_price_window(client: TestClient) -> tuple[float, list[dict[str, Any]]]:
    base = faker.pyfloat(min_value=1e6, max_value=1e7, right_digits=0)
    items = [
        client.post("/item", json={"name": f"window {i}", "price": base + i}).json()
        for i in range(5)
    ]
    return base, items


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("get", f"/item/{NOT_EXISTING_ID}", None),
        ("put", f"/item/{NOT_EXISTING_ID}", {"name": "name", "price": 1.0}),
        ("patch", f"/item/{NOT_EXISTING_ID}", {"price": 1.0}),
        ("delete", f"/item/{NOT_EXISTING_ID}", None),
        ("get", f"/cart/{NOT_EXISTING_ID}", None),
        ("post", f"/cart/{NOT_EXISTING_ID}/add/1", None),
    ],
)
def test_not_found(
    client: TestClient, method: str, url: str, body: dict | None
) -> None:
    response = client.request(method, url, json=body)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_not_existing_item_to_cart(client: TestClient, cart_id: int) -> None:
    response = client.post(f"/cart/{cart_id}/add/{NOT_EXISTING_ID}")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert client.get(f"/cart/{cart_id}").json()["items"] == []


def test_get_deleted_item(client: TestClient, deleted_item: dict[str, Any]) -> None:
    response = client.get(f"/item/{deleted_item['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "no price"},
        {"price": 1.0},
        {"name": "negative price", "price": -1.0},
        {"name": "bad price", "price": "abc"},
    ],
)
def test_post_item_invalid(client: TestClient, body: dict[str, Any]) -> None:
    response = client.post("/item", json=body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_post_item_returns_new_item(client: TestClient) -> None:
    response = client.post("/item", json={"name": "new", "price": 0.0})

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["name"] == "new"
    assert data["price"] == 0.0
    assert data["deleted"] is False
    assert client.get(f"/item/{data['id']}").json() == data


def test_put_deleted_item(client: TestClient, deleted_item: dict[str, Any]) -> None:
    response = client.put(
        f"/item/{deleted_item['id']}", json={"name": "renamed", "price": 1.0}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": deleted_item["id"],
        "name": "renamed",
        "price": 1.0,
        "deleted": True,
    }


@pytest.mark.parametrize(
    "body",
    [
        {"name": "only name"},
        {"price": 42.0},
        {"name": "both", "price": 42.0},
    ],
)
def test_patch_item_changes_only_passed_fields(
    client: TestClient, item: dict[str, Any], body: dict[str, Any]
) -> None:
    response = client.patch(f"/item/{item['id']}", json=body)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {**item, **body}
    assert client.get(f"/item/{item['id']}").json() == {**item, **body}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "new name"},
        {"name": "new name", "price": 9.99},
    ],
)
def test_patch_deleted_item(
    client: TestClient, deleted_item: dict[str, Any], body: dict[str, Any]
) -> None:
    response = client.patch(f"/item/{deleted_item['id']}", json=body)

    assert response.status_code == HTTPStatus.NOT_MODIFIED
    items = client.get("/item", params={"show_deleted": True, "limit": 10_000})
    assert deleted_item in items.json()


def test_patch_item_negative_price(client: TestClient, item: dict[str, Any]) -> None:
    response = client.patch(f"/item/{item['id']}", json={"price": -1.0})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.get(f"/item/{item['id']}").json() == item


def test_get_item_list_pagination(
    client: TestClient, items_in_price_window: tuple[float, list[dict[str, Any]]]
) -> None:
    base, items = items_in_price_window

    response = client.get(
        "/item",
        params={"min_price": base, "max_price": base + 4, "offset": 1, "limit": 2},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == items[1:3]


@pytest.mark.parametrize(
    ("show_deleted", "expected_in_list"),
    [
        (False, False),
        (True, True),
    ],
)
def test_get_item_list_show_deleted(
    client: TestClient,
    deleted_item: dict[str, Any],
    show_deleted: bool,
    expected_in_list: bool,
) -> None:
    response = client.get(
        "/item",
        params={
            "show_deleted": show_deleted,
            "min_price": deleted_item["price"],
            "max_price": deleted_item["price"],
            "limit": 1000,
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert (deleted_item in response.json()) is expected_in_list


def test_post_cart(client: TestClient) -> None:
    response = client.post("/cart")

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert response.headers["location"] == f"/cart/{data['id']}"
    assert data == {"id": data["id"], "items": [], "price": 0.0}


def test_add_same_item_twice(
    client: TestClient, cart_id: int, item: dict[str, Any]
) -> None:
    for _ in range(2):
        assert (
            client.post(f"/cart/{cart_id}/add/{item['id']}").status_code
            == HTTPStatus.OK
        )

    cart = client.get(f"/cart/{cart_id}").json()

    assert cart["items"] == [
        {"id": item["id"], "name": item["name"], "quantity": 2, "available": True}
    ]
    assert cart["price"] == pytest.approx(item["price"] * 2)


def test_cart_with_deleted_item(
    client: TestClient,
    cart_id: int,
    item: dict[str, Any],
    another_item: dict[str, Any],
) -> None:
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    client.post(f"/cart/{cart_id}/add/{another_item['id']}")
    client.delete(f"/item/{another_item['id']}")

    cart = client.get(f"/cart/{cart_id}").json()

    availability = {i["id"]: i["available"] for i in cart["items"]}
    assert availability == {item["id"]: True, another_item["id"]: False}
    assert cart["price"] == pytest.approx(item["price"])


@pytest.mark.parametrize(
    ("query", "expected_in_list"),
    [
        ({"min_quantity": 3}, True),
        ({"min_quantity": 4}, False),
        ({"max_quantity": 3}, True),
        ({"max_quantity": 2}, False),
    ],
)
def test_get_cart_list_quantity_filter(
    client: TestClient,
    cart_id: int,
    item: dict[str, Any],
    query: dict[str, int],
    expected_in_list: bool,
) -> None:
    for _ in range(3):
        client.post(f"/cart/{cart_id}/add/{item['id']}")

    response = client.get("/cart", params={**query, "limit": 10_000})

    assert response.status_code == HTTPStatus.OK
    carts = response.json()
    quantities = [sum(i["quantity"] for i in c["items"]) for c in carts]
    if "min_quantity" in query:
        assert all(q >= query["min_quantity"] for q in quantities)
    if "max_quantity" in query:
        assert all(q <= query["max_quantity"] for q in quantities)
    assert (cart_id in {c["id"] for c in carts}) is expected_in_list


def test_get_cart_list_price_filter(
    client: TestClient, cart_id: int, item: dict[str, Any]
) -> None:
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    response = client.get(
        "/cart",
        params={
            "min_price": item["price"],
            "max_price": item["price"],
            "limit": 10_000,
        },
    )

    assert response.status_code == HTTPStatus.OK
    carts = response.json()
    assert all(c["price"] == pytest.approx(item["price"]) for c in carts)
    assert cart_id in {c["id"] for c in carts}


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        (ListParams(), [1.0, 2.0, 3.0, 4.0, 5.0]),
        (ListParams(offset=1, limit=2), [2.0, 3.0]),
        (ListParams(offset=10), []),
        (ListParams(min_price=2.0, max_price=4.0), [2.0, 3.0, 4.0]),
        (ListParams(min_price=4.0, limit=1), [4.0]),
        (ListParams(max_price=0.5), []),
    ],
)
def test_apply_list_params(params: ListParams, expected: list[float]) -> None:
    objs = [Priced(price) for price in [1.0, 2.0, 3.0, 4.0, 5.0]]

    result = apply_list_params(objs, params)

    assert [o.price for o in result] == expected


def test_cart_quantity() -> None:
    cart = Cart(
        id=1,
        items=[
            CartItem(id=1, name="a", quantity=2),
            CartItem(id=2, name="b", quantity=3, available=False),
        ],
        price=0.0,
    )

    assert cart.quantity == 5


def test_metrics(client: TestClient) -> None:
    response = client.get("/metrics")

    assert response.status_code == HTTPStatus.OK
    assert "http_requests_total" in response.text
