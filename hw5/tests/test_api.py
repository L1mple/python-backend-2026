import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("method", "path", "body", "expected"),
    [
        ("GET", "/cart/0", None, 404),
        ("GET", "/item/0", None, 404),
        ("PUT", "/item/0", {"name": "Missing", "price": 10}, 404),
        ("PATCH", "/item/0", {"price": 10}, 304),
        ("DELETE", "/item/0", None, 200),
        ("POST", "/cart/0/add/0", None, 404),
    ],
)
def test_missing_resources(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, object] | None,
    expected: int,
) -> None:
    response = client.request(method, path, json=body)
    assert response.status_code == expected
    assert client.get("/item").json() == []
    assert client.get("/cart").json() == []


@pytest.mark.parametrize(
    "patch", [{"name": None}, {"price": None}, {"name": None, "price": None}]
)
def test_patch_rejects_explicit_null_without_changing_item(
    client: TestClient, patch: dict[str, None]
) -> None:
    original = client.post("/item", json={"name": "Tea", "price": 25}).json()
    response = client.patch(f"/item/{original['id']}", json=patch)
    assert response.status_code == 422
    assert client.get(f"/item/{original['id']}").json() == original


def test_cannot_add_missing_item_to_existing_cart(client: TestClient) -> None:
    cart_id = client.post("/cart").json()["id"]
    assert client.post(f"/cart/{cart_id}/add/0").status_code == 404
    assert client.get(f"/cart/{cart_id}").json() == {
        "id": cart_id,
        "items": [],
        "price": 0,
    }


def test_deleted_item_cannot_be_replaced_or_patched(client: TestClient) -> None:
    item = client.post("/item", json={"name": "Tea", "price": 25}).json()
    path = f"/item/{item['id']}"
    assert client.delete(path).status_code == 200
    assert client.put(path, json={"name": "New", "price": 1}).status_code == 404
    assert client.patch(path, json={"price": 1}).status_code == 304
    assert client.get(path).status_code == 404
    assert client.get("/item?show_deleted=true").json() == [item | {"deleted": True}]


def test_item_filters_are_inclusive_and_pagination_is_stable(
    client: TestClient,
) -> None:
    items = [
        client.post("/item", json={"name": name, "price": price}).json()
        for name, price in (("Cheap", 5), ("Middle", 10), ("Expensive", 20))
    ]
    assert client.get("/item?min_price=5&max_price=10").json() == items[:2]
    assert client.get("/item?offset=1&limit=1").json() == [items[1]]
    assert client.get("/item?min_price=21").json() == []
    client.delete(f"/item/{items[1]['id']}")
    assert client.get("/item").json() == [items[0], items[2]]


def test_cart_quantity_filters_count_units_and_keep_empty_carts(
    client: TestClient,
) -> None:
    item_id = client.post("/item", json={"name": "Milk", "price": 10}).json()["id"]
    cart_ids = [client.post("/cart").json()["id"] for _ in range(3)]
    client.post(f"/cart/{cart_ids[1]}/add/{item_id}")
    for _ in range(2):
        client.post(f"/cart/{cart_ids[2]}/add/{item_id}")
    assert [
        cart["id"] for cart in client.get("/cart?min_quantity=2&max_quantity=2").json()
    ] == [cart_ids[2]]
    assert [
        cart["id"] for cart in client.get("/cart?min_price=0&max_price=0").json()
    ] == [cart_ids[0]]
    assert client.get("/cart?min_price=30").json() == []


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/item", {"name": "Tea", "price": -1}),
        ("POST", "/item", {"name": "Tea", "price": None}),
        ("POST", "/item", {"name": "Tea", "price": 1, "deleted": True}),
        ("GET", "/item/not-an-id", None),
        ("GET", "/cart?max_quantity=-1", None),
    ],
)
def test_invalid_requests_do_not_create_data(
    client: TestClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    assert client.request(method, path, json=body).status_code == 422
    assert client.get("/item").json() == []
    assert client.get("/cart").json() == []
