from http import HTTPStatus

from fastapi.testclient import TestClient

from shop_api.main import app

client = TestClient(app)

MISSING_ID = 10**9


def test_get_missing_cart() -> None:
    response = client.get(f"/cart/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_to_missing_cart() -> None:
    item_id = client.post("/item", json={"name": "a", "price": 1.0}).json()["id"]

    response = client.post(f"/cart/{MISSING_ID}/add/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item_to_cart() -> None:
    cart_id = client.post("/cart").json()["id"]

    response = client.post(f"/cart/{cart_id}/add/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_missing_item() -> None:
    response = client.patch(f"/item/{MISSING_ID}", json={"price": 1.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_missing_item() -> None:
    response = client.delete(f"/item/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_deleted_item() -> None:
    item_id = client.post("/item", json={"name": "a", "price": 1.0}).json()["id"]
    client.delete(f"/item/{item_id}")

    response = client.put(f"/item/{item_id}", json={"name": "b", "price": 2.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_same_item_twice() -> None:
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "a", "price": 10.0}).json()["id"]

    client.post(f"/cart/{cart_id}/add/{item_id}")
    cart = client.post(f"/cart/{cart_id}/add/{item_id}").json()

    assert cart["items"] == [{"id": item_id, "name": "a", "quantity": 2, "available": True}]
    assert cart["price"] == 20.0


def test_deleted_item_in_cart() -> None:
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "a", "price": 10.0}).json()["id"]
    client.post(f"/cart/{cart_id}/add/{item_id}")

    client.delete(f"/item/{item_id}")
    cart = client.get(f"/cart/{cart_id}").json()

    # silinen urun sepette kaliyor ama fiyata girmiyor
    assert cart["items"][0]["available"] is False
    assert cart["price"] == 0.0
