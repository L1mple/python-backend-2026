from http import HTTPStatus
from typing import Any
from fastapi.testclient import TestClient


MISSING_ID = 67


def _create_item(client: TestClient, name: str = "Товар", price: float = 10.0) -> dict:
    response = client.post("/item", json={"name": name, "price": price})
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


def _create_cart(client: TestClient) -> int:
    response = client.post("/cart")
    assert response.status_code == HTTPStatus.CREATED
    return response.json()["id"]


def _deleted_item(client: TestClient) -> dict:
    item = _create_item(client)
    assert client.delete(f"/item/{item['id']}").status_code == HTTPStatus.OK
    return item


def _cart_ids(client: TestClient, params: dict[str, Any]) -> list[int]:
    return [cart["id"] for cart in client.get("/cart", params=params).json()]


def test_cart_location_header(client: TestClient) -> None:
    response = client.post("/cart")
    assert response.status_code == HTTPStatus.CREATED
    assert response.headers["location"] == f"/cart/{response.json()['id']}"


def test_get_item_missing(client: TestClient) -> None:
    assert client.get(f"/item/{MISSING_ID}").status_code == HTTPStatus.NOT_FOUND


def test_get_item_deleted(client: TestClient) -> None:
    item = _deleted_item(client)
    assert client.get(f"/item/{item['id']}").status_code == HTTPStatus.NOT_FOUND


def test_put_item_missing(client: TestClient) -> None:
    response = client.put(
        f"/item/{MISSING_ID}", json={"name": "Имя", "price": 1.0}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_item_deleted(client: TestClient) -> None:
    item = _deleted_item(client)
    response = client.put(
        f"/item/{item['id']}", json={"name": "Имя", "price": 1.0}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_item_missing(client: TestClient) -> None:
    response = client.patch(f"/item/{MISSING_ID}", json={"name": "Имя"})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_item_deleted(client: TestClient) -> None:
    item = _deleted_item(client)
    response = client.patch(f"/item/{item['id']}", json={"name": "Имя"})
    assert response.status_code == HTTPStatus.NOT_MODIFIED


def test_patch_forbids_deleted(client: TestClient) -> None:
    item = _create_item(client)
    response = client.patch(f"/item/{item['id']}", json={"deleted": True})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_delete_item_missing(client: TestClient) -> None:
    assert client.delete(f"/item/{MISSING_ID}").status_code == HTTPStatus.OK


def test_get_cart_missing(client: TestClient) -> None:
    assert client.get(f"/cart/{MISSING_ID}").status_code == HTTPStatus.NOT_FOUND


def test_add_missing_cart(client: TestClient) -> None:
    item = _create_item(client)
    response = client.post(f"/cart/{MISSING_ID}/add/{item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item(client: TestClient) -> None:
    cart_id = _create_cart(client)
    response = client.post(f"/cart/{cart_id}/add/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_deleted_item(client: TestClient) -> None:
    cart_id = _create_cart(client)
    item = _deleted_item(client)
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_cart_deleted_price(
    client: TestClient,
) -> None:
    cart_id = _create_cart(client)
    alive = _create_item(client, "Живой", 100.0)
    removed = _create_item(client, "Удалённый", 50.0)
    client.post(f"/cart/{cart_id}/add/{alive['id']}")
    client.post(f"/cart/{cart_id}/add/{removed['id']}")
    client.delete(f"/item/{removed['id']}")
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["price"] == 100.0
    availability = {entry["id"]: entry["available"] for entry in cart["items"]}
    assert availability == {alive["id"]: True, removed["id"]: False}


def test_add_twice_quantity(client: TestClient) -> None:
    cart_id = _create_cart(client)
    item = _create_item(client, "Товар", 25.0)
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")
    assert response.status_code == HTTPStatus.OK
    cart = response.json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 2
    assert cart["price"] == 50.0


def test_empty_cart_price(client: TestClient) -> None:
    cart_id = _create_cart(client)
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart == {"id": cart_id, "items": [], "price": 0.0}


def test_items_show_deleted(client: TestClient) -> None:
    alive = _create_item(client, "Живой", 10.0)
    removed = _deleted_item(client)
    visible = client.get("/item").json()
    assert [entry["id"] for entry in visible] == [alive["id"]]
    with_deleted = client.get("/item", params={"show_deleted": True}).json()
    assert {entry["id"] for entry in with_deleted} == {alive["id"], removed["id"]}


def test_metrics_exposed(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == HTTPStatus.OK
    assert "http_requests_total" in response.text


def test_negative_price(client: TestClient) -> None:
    response = client.post("/item", json={"name": "Товар", "price": -1.0})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_cart_list_filters(client: TestClient) -> None:
    empty_cart_id = _create_cart(client)
    full_cart_id = _create_cart(client)
    item = _create_item(client, "Товар", 100.0)
    client.post(f"/cart/{full_cart_id}/add/{item['id']}")
    assert _cart_ids(client, {"min_quantity": 1}) == [full_cart_id]
    assert _cart_ids(client, {"max_quantity": 0}) == [empty_cart_id]
    assert _cart_ids(client, {"min_price": 100.0}) == [full_cart_id]
    assert _cart_ids(client, {"max_price": 0.0}) == [empty_cart_id]
