from typing import Any

import pytest
from fastapi.testclient import TestClient


def create_item(client: TestClient, name: str, price: float) -> dict[str, Any]:
    response = client.post("/item", json={"name": name, "price": price})
    assert response.status_code == 201
    item = response.json()
    assert response.headers["location"] == f"/item/{item['id']}"
    return item


def create_cart(client: TestClient, item_ids: tuple[int, ...] = ()) -> int:
    response = client.post("/cart")
    assert response.status_code == 201
    cart_id = response.json()["id"]
    assert response.headers["location"] == f"/cart/{cart_id}"
    for item_id in item_ids:
        assert client.post(f"/cart/{cart_id}/add/{item_id}").status_code == 200
    return cart_id


def test_item_filters_and_pagination(client: TestClient) -> None:
    items = [create_item(client, f"Item {index}", index * 10) for index in range(5)]
    assert client.delete(f"/item/{items[1]['id']}").status_code == 200
    items[1]["deleted"] = True

    cases = [
        ({}, [0, 2, 3, 4]),
        ({"show_deleted": False}, [0, 2, 3, 4]),
        ({"show_deleted": True}, [0, 1, 2, 3, 4]),
        ({"min_price": 20}, [2, 3, 4]),
        ({"max_price": 20}, [0, 2]),
        ({"min_price": 20, "max_price": 30}, [2, 3]),
        ({"min_price": 0, "max_price": 0}, [0]),
        ({"offset": 1, "limit": 2}, [2, 3]),
        ({"min_price": 20, "offset": 1, "limit": 1}, [3]),
        ({"show_deleted": True, "min_price": 10, "max_price": 10}, [1]),
        ({"min_price": 30, "max_price": 20}, []),
        ({"offset": 5}, []),
    ]
    for query, expected_indices in cases:
        response = client.get("/item", params=query)
        assert response.status_code == 200, query
        assert response.json() == [items[index] for index in expected_indices], query


@pytest.mark.parametrize("resource", ["item", "cart"])
def test_default_page_size(client: TestClient, resource: str) -> None:
    if resource == "item":
        ids = [create_item(client, f"Item {index}", index)["id"] for index in range(12)]
    else:
        ids = [create_cart(client) for _ in range(12)]

    response = client.get(f"/{resource}")
    assert response.status_code == 200
    assert [entry["id"] for entry in response.json()] == ids[:10]

    response = client.get(f"/{resource}", params={"offset": 10})
    assert response.status_code == 200
    assert [entry["id"] for entry in response.json()] == ids[10:]


def test_cart_filters_and_pagination(client: TestClient) -> None:
    cheap = create_item(client, "Cheap", 10)["id"]
    expensive = create_item(client, "Expensive", 30)["id"]
    deleted = create_item(client, "Deleted", 100)["id"]
    cart_ids = [
        create_cart(client),
        create_cart(client, (cheap,)),
        create_cart(client, (cheap, cheap)),
        create_cart(client, (expensive,)),
        create_cart(client, (deleted, deleted)),
        create_cart(client, (cheap, deleted)),
    ]
    assert client.delete(f"/item/{deleted}").status_code == 200
    carts = [client.get(f"/cart/{cart_id}").json() for cart_id in cart_ids]
    assert [cart["price"] for cart in carts] == [0, 10, 20, 30, 0, 10]
    assert [sum(item["quantity"] for item in cart["items"]) for cart in carts] == [
        0, 1, 2, 1, 2, 2
    ]

    cases = [
        ({}, [0, 1, 2, 3, 4, 5]),
        ({"min_price": 20}, [2, 3]),
        ({"max_price": 10}, [0, 1, 4, 5]),
        ({"min_price": 10, "max_price": 20}, [1, 2, 5]),
        ({"min_price": 0, "max_price": 0}, [0, 4]),
        ({"min_quantity": 2}, [2, 4, 5]),
        ({"max_quantity": 1}, [0, 1, 3]),
        ({"min_quantity": 1, "max_quantity": 1}, [1, 3]),
        ({"max_quantity": 0}, [0]),
        ({"min_price": 10, "max_price": 20, "min_quantity": 2}, [2, 5]),
        ({"min_quantity": 2, "offset": 1, "limit": 1}, [4]),
        ({"offset": 2, "limit": 2}, [2, 3]),
        ({"min_price": 30, "max_price": 10}, []),
        ({"min_quantity": 3, "max_quantity": 1}, []),
        ({"offset": 6}, []),
    ]
    for query, expected_indices in cases:
        response = client.get("/cart", params=query)
        assert response.status_code == 200, query
        assert response.json() == [carts[index] for index in expected_indices], query


def test_cart_tracks_item_quantity_and_changes(client: TestClient) -> None:
    first = create_item(client, "First", 12.5)
    second = create_item(client, "Second", 4)
    cart_id = create_cart(client)
    cart_url = f"/cart/{cart_id}"
    first_url = f"/item/{first['id']}"
    assert client.get(cart_url).json() == {"id": cart_id, "items": [], "price": 0}

    for quantity in (1, 2):
        response = client.post(f"{cart_url}/add/{first['id']}")
        assert response.status_code == 200
        assert response.json() == {
            "id": cart_id,
            "items": [
                {"id": first["id"], "name": "First", "quantity": quantity, "available": True}
            ],
            "price": 12.5 * quantity,
        }

    assert client.post(f"{cart_url}/add/{second['id']}").status_code == 200
    assert client.patch(first_url, json={"name": "Updated", "price": 20}).status_code == 200
    expected = {
        "id": cart_id,
        "items": [
            {"id": first["id"], "name": "Updated", "quantity": 2, "available": True},
            {"id": second["id"], "name": "Second", "quantity": 1, "available": True},
        ],
        "price": 44,
    }
    assert client.get(cart_url).json() == expected

    assert client.delete(first_url).status_code == 200
    assert client.post(f"{cart_url}/add/{first['id']}").status_code == 404
    expected["items"][0]["available"] = False
    expected["price"] = 4
    assert client.get(cart_url).json() == expected
    assert client.get("/cart").json() == [expected]

    response = client.put(first_url, json={"name": "Restored", "price": 3})
    assert response.status_code == 200
    assert response.json() == {
        "id": first["id"], "name": "Restored", "price": 3, "deleted": False
    }
    expected["items"][0].update(name="Restored", available=True)
    expected["price"] = 10
    assert client.get(cart_url).json() == expected


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/cart/2147483647", None),
        ("GET", "/item/2147483647", None),
        ("PUT", "/item/2147483647", {"name": "Missing", "price": 1}),
        ("PATCH", "/item/2147483647", {"name": "Missing"}),
        ("DELETE", "/item/2147483647", None),
    ],
)
def test_missing_resource(
    client: TestClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    assert client.request(method, path, json=body).status_code == 404
    assert client.get("/item").json() == []
    assert client.get("/cart").json() == []


def test_add_missing_item_or_cart(client: TestClient) -> None:
    item = create_item(client, "Existing", 10)
    cart_id = create_cart(client)

    assert client.post(f"/cart/2147483647/add/{item['id']}").status_code == 404
    assert client.post(f"/cart/{cart_id}/add/2147483647").status_code == 404
    assert client.get(f"/cart/{cart_id}").json() == {
        "id": cart_id, "items": [], "price": 0
    }


@pytest.mark.parametrize(
    "body",
    [
        {"name": None},
        {"price": None},
        {"price": -1},
        {"price": "NaN"},
        {"price": "Infinity"},
        {"deleted": True},
        {"id": 999},
        {"unknown": "value"},
    ],
)
def test_invalid_patch_keeps_item_unchanged(client: TestClient, body: dict[str, Any]) -> None:
    item = create_item(client, "Original", 10)
    item_url = f"/item/{item['id']}"

    response = client.patch(item_url, json=body)

    assert response.status_code == 422
    assert client.get(item_url).json() == item


def test_patch_preserves_omitted_fields(client: TestClient) -> None:
    item = create_item(client, "Original", 10)
    item_url = f"/item/{item['id']}"

    for body in ({}, {"name": ""}, {"price": 0}):
        response = client.patch(item_url, json=body)
        item.update(body)
        assert response.status_code == 200
        assert response.json() == item
        assert client.get(item_url).json() == item


def test_deleted_item_cannot_be_patched(client: TestClient) -> None:
    item = create_item(client, "Original", 10)
    item_url = f"/item/{item['id']}"
    assert client.delete(item_url).status_code == 200

    response = client.patch(item_url, json={"name": "Changed", "price": 0})

    assert response.status_code == 304
    assert response.content == b""
    assert client.get(item_url).status_code == 404
    item["deleted"] = True
    assert client.get("/item", params={"show_deleted": True}).json() == [item]


@pytest.mark.parametrize("resource", ["item", "cart"])
@pytest.mark.parametrize("bound", ["min_price", "max_price"])
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_price_filter_is_rejected(
    client: TestClient, resource: str, bound: str, value: str
) -> None:
    assert client.get(f"/{resource}", params={bound: value}).status_code == 422
