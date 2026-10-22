from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient


def test_creation_locations_and_unique_ids(client: TestClient) -> None:
    cart = client.post("/cart")
    assert cart.status_code == HTTPStatus.CREATED
    assert client.get(cart.headers["location"]).json() == {
        "id": cart.json()["id"],
        "items": [],
        "price": 0.0,
    }
    assert client.post("/cart").json()["id"] != cart.json()["id"]

    item = client.post("/item", json={"name": "Milk", "price": 0})
    assert item.status_code == HTTPStatus.CREATED
    assert client.get(item.headers["location"]).json() == item.json()
    assert item.json()["deleted"] is False


@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"])
def test_missing_item(client: TestClient, method: str) -> None:
    response = client.request(method, "/item/999", json={"name": "Milk", "price": 10})
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert client.get("/item", params={"show_deleted": True}).json() == []


@pytest.mark.parametrize(
    "path", ["/cart/999", "/cart/999/add/1", "/cart/1/add/999"]
)
def test_missing_cart_or_item(client: TestClient, path: str) -> None:
    client.post("/cart")
    client.post("/item", json={"name": "Milk", "price": 10})
    response = client.get(path) if "/add/" not in path else client.post(path)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert client.get("/cart/1").json()["items"] == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "Milk"},
        {"name": "", "price": 10},
        {"name": "  ", "price": 10},
        {"name": None, "price": 10},
        {"name": "Milk", "price": -1},
        {"name": "Milk", "price": None},
        {"name": "Milk", "price": "NaN"},
        {"name": "Milk", "price": "Infinity"},
        {"name": "Milk", "price": 10, "id": 50},
    ],
)
def test_invalid_item_does_not_change_store(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/item", json=body).status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    item = client.post("/item", json={"name": "Milk", "price": 10}).json()
    assert client.put(f"/item/{item['id']}", json=body).status_code == 422
    assert client.get(f"/item/{item['id']}").json() == item


@pytest.mark.parametrize("body", [{"name": None}, {"price": None}, {"id": 1}, {"deleted": False}])
def test_invalid_patch(client: TestClient, body: dict[str, Any]) -> None:
    item = client.post("/item", json={"name": "Milk", "price": 10}).json()
    assert client.patch(f"/item/{item['id']}", json=body).status_code == 422
    assert client.get(f"/item/{item['id']}").json() == item


def test_patch_preserves_omitted_fields_and_accepts_zero(client: TestClient) -> None:
    item = client.post("/item", json={"name": "Milk", "price": 10}).json()
    path = f"/item/{item['id']}"
    assert client.patch(path, json={}).json() == item
    item["price"] = 0.0
    assert client.patch(path, json={"price": 0}).json() == item
    item["name"] = "Tea"
    assert client.patch(path, json={"name": "Tea"}).json() == item


def test_cart_tracks_quantity_price_and_availability(client: TestClient) -> None:
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "Milk", "price": 10}).json()["id"]
    path = f"/cart/{cart_id}"
    client.post(f"{path}/add/{item_id}")
    cart = client.post(f"{path}/add/{item_id}").json()
    assert cart["price"] == 20
    assert cart["items"] == [{"id": item_id, "name": "Milk", "quantity": 2, "available": True}]

    client.patch(f"/item/{item_id}", json={"name": "Tea", "price": 15})
    cart = client.get(path).json()
    assert cart["price"] == 30
    assert cart["items"][0]["name"] == "Tea"

    for _ in range(2):
        assert client.delete(f"/item/{item_id}").status_code == HTTPStatus.OK
    assert client.get(f"/item/{item_id}").status_code == HTTPStatus.NOT_FOUND
    assert client.post(f"{path}/add/{item_id}").status_code == HTTPStatus.NOT_FOUND
    cart = client.get(path).json()
    assert cart["price"] == 0
    assert cart["items"][0]["available"] is False
    assert cart["items"][0]["quantity"] == 2
    assert client.get("/item").json() == []
    assert client.get("/item", params={"show_deleted": True}).json()[0]["deleted"] is True
    response = client.patch(f"/item/{item_id}", json={"price": 1})
    assert response.status_code == HTTPStatus.NOT_MODIFIED
    assert response.content == b""


def test_put_replaces_deleted_flag_without_creating_missing_items(client: TestClient) -> None:
    item_id = client.post("/item", json={"name": "Milk", "price": 10}).json()["id"]
    path = f"/item/{item_id}"
    response = client.put(path, json={"name": "Tea", "price": 20, "deleted": True})
    assert response.json() == {"id": item_id, "name": "Tea", "price": 20, "deleted": True}
    assert client.get(path).status_code == 404
    response = client.put(path, json={"name": "Tea", "price": 0})
    assert response.json()["deleted"] is False
    assert client.get(path).json() == response.json()


def test_item_filters_are_inclusive_and_precede_pagination(client: TestClient) -> None:
    items = [client.post("/item", json={"name": str(i), "price": i}).json() for i in range(15)]
    client.delete(f"/item/{items[0]['id']}")
    assert client.get("/item").json() == items[1:11]
    params = {"min_price": 3, "max_price": 7, "offset": 1, "limit": 2}
    assert client.get("/item", params=params).json() == items[4:6]
    assert client.get("/item", params={"offset": 999}).json() == []
    assert client.get("/item", params={"min_price": 7, "max_price": 3}).json() == []


def test_cart_filters_use_each_cart_and_precede_pagination(client: TestClient) -> None:
    item_id = client.post("/item", json={"name": "Milk", "price": 10}).json()["id"]
    carts = []
    for quantity in range(5):
        cart_id = client.post("/cart").json()["id"]
        for _ in range(quantity):
            client.post(f"/cart/{cart_id}/add/{item_id}")
        carts.append(client.get(f"/cart/{cart_id}").json())
    params = {"min_price": 10, "max_price": 30, "min_quantity": 1, "max_quantity": 3}
    assert client.get("/cart", params=params).json() == carts[1:4]
    assert client.get("/cart", params={**params, "offset": 1, "limit": 1}).json() == carts[2:3]
    assert client.get("/cart", params={"min_quantity": 0, "max_quantity": 0}).json() == carts[:1]


@pytest.mark.parametrize("path", ["/cart", "/item"])
@pytest.mark.parametrize(
    "query",
    [{"min_price": "nan"}, {"max_price": "inf"}, {"limit": "1.5"}, {"offset": "no"}],
)
def test_invalid_query_parameters(client: TestClient, path: str, query: dict[str, str]) -> None:
    assert client.get(path, params=query).status_code == HTTPStatus.UNPROCESSABLE_ENTITY
