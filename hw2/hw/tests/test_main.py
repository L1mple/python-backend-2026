from http import HTTPStatus
import pytest
from fastapi.testclient import TestClient
from shop_api.main import app

client = TestClient(app)

def create_item(name = "Test item 1", price = 1.01) -> tuple[dict, dict]:
    item = {
        "name": name,
        "price": price,
    }
    response = client.post("/item", json = item)
    assert response.status_code == HTTPStatus.CREATED
    return item, response.json()


def create_cart() -> int:
    response = client.post("/cart")
    assert response.status_code == HTTPStatus.CREATED
    return response.json()["id"]


def test_metrics_available() -> None:
    response = client.get("/metrics")

    assert response.status_code == HTTPStatus.OK
    assert "text/plain" in response.headers["content-type"]


def test_create_item() -> None:
    item, json = create_item()
    assert json["id"] > 0
    assert json["name"] == item["name"]
    assert json["price"] == item["price"]
    assert json["deleted"] is False


def test_item_full_cycle() -> None:
    item, json = create_item()
    item_id = json["id"]
    get_response = client.get(f"/item/{item_id}")
    assert get_response.status_code == HTTPStatus.OK
    assert get_response.json() == json

    list_response = client.get("/item", params = {"limit": 10000, "show_deleted": True})
    assert list_response.status_code == HTTPStatus.OK
    assert json in list_response.json()

    item = {
        "name": "Updated item",
        "price": 2026.,
    }
    put_response = client.put(f"/item/{item_id}", json = item)
    assert put_response.status_code == HTTPStatus.OK
    assert put_response.json() == {"id": item_id, **item, "deleted": False}

    item = {"price": 0.99}
    patch_response = client.patch(f"/item/{item_id}", json = item)
    assert patch_response.status_code == HTTPStatus.OK
    assert patch_response.json()["price"] == item["price"]

    delete_response = client.delete(f"/item/{item_id}")
    assert delete_response.status_code == HTTPStatus.OK
    assert client.get(f"/item/{item_id}").status_code == HTTPStatus.NOT_FOUND


def test_create_and_get_cart() -> None:
    cart_id = create_cart()
    get_response = client.get(f"/cart/{cart_id}")
    assert get_response.status_code == HTTPStatus.OK
    assert get_response.json() == {
        "id": cart_id,
        "items": [],
        "price": 0.0,
    }
    list_response = client.get("/cart", params = {"limit": 1})
    assert list_response.status_code == HTTPStatus.OK
    assert isinstance(list_response.json(), list)


def test_add_item_to_cart_multiple() -> None:
    item, json = create_item()
    cart_id = create_cart()
    for i in range(1, 10):
        response = client.post(f"/cart/{cart_id}/add/{json['id']}")
        assert response.status_code == HTTPStatus.OK
        cart = response.json()
        assert cart["id"] == cart_id
        assert cart["items"] == [
            {
                "id": json["id"],
                "name": json["name"],
                "quantity": i,
                "available": True,
            }
        ]
        assert cart["price"] == json["price"] * i


def test_db() -> None:
    item, json = create_item("Test db item", 239)
    items = client.get(
        "/item",
        params = {
            "min_price": 0,
            "max_price": 1,
            "show_deleted": False,
        },
    )
    assert items.status_code == HTTPStatus.OK
    assert json not in items.json()

    matching_items = client.get(
        "/item",
        params = {
            "min_price": 238,
            "max_price": 240,
            "show_deleted": False,
        },
    )
    assert matching_items.status_code == HTTPStatus.OK
    assert json in matching_items.json()

    assert client.get("/cart/-1").status_code == HTTPStatus.NOT_FOUND
    assert client.post("/cart/-1/add/-1").status_code == HTTPStatus.NOT_FOUND
    assert client.put("/item/-1", json = {"name": "Missing", "price": 4.04}).status_code == HTTPStatus.NOT_MODIFIED
    assert client.patch("/item/-1", json = {"name": "Missing"}).status_code == HTTPStatus.NOT_MODIFIED
