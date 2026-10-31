from http import HTTPStatus

from fastapi.testclient import TestClient

from shop_api.contracts import CartResponse
from shop_api.main import app
from shop_api.store import CartRecord

client = TestClient(app)

MISSING_ID = 1_000_000_000


def new_item() -> int:
    return client.post("/item", json={"name": "Тестовый товар", "price": 100.0}).json()["id"]


def new_deleted_item() -> int:
    item_id = new_item()
    client.delete(f"/item/{item_id}")
    return item_id


def new_cart() -> int:
    return client.post("/cart").json()["id"]


def test_lifespan_starts_app() -> None:
    with TestClient(app) as lifespan_client:
        assert lifespan_client.get("/item").status_code == HTTPStatus.OK


def test_get_missing_cart() -> None:
    assert client.get(f"/cart/{MISSING_ID}").status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_missing_cart() -> None:
    response = client.post(f"/cart/{MISSING_ID}/add/{new_item()}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item_to_cart() -> None:
    response = client.post(f"/cart/{new_cart()}/add/{MISSING_ID}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_deleted_item_to_cart() -> None:
    response = client.post(f"/cart/{new_cart()}/add/{new_deleted_item()}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_same_item_twice() -> None:
    cart_id, item_id = new_cart(), new_item()
    client.post(f"/cart/{cart_id}/add/{item_id}")
    response = client.post(f"/cart/{cart_id}/add/{item_id}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["items"] == [
        {"id": item_id, "name": "Тестовый товар", "quantity": 2, "available": True}
    ]
    assert response.json()["price"] == 200.0


def test_put_missing_item() -> None:
    response = client.put(f"/item/{MISSING_ID}", json={"name": "x", "price": 1.0})
    assert response.status_code == HTTPStatus.NOT_MODIFIED


def test_put_deleted_item() -> None:
    response = client.put(f"/item/{new_deleted_item()}", json={"name": "x", "price": 1.0})
    assert response.status_code == HTTPStatus.NOT_MODIFIED


def test_delete_missing_item() -> None:
    assert client.delete(f"/item/{MISSING_ID}").status_code == HTTPStatus.NOT_FOUND


def test_cart_response_skips_missing_item() -> None:
    """Защитная ветка: в корзине id товара, которого нет в базе (через API так не сделать)."""
    cart = CartResponse.from_record(CartRecord(id=1, items={MISSING_ID: 1}))
    assert cart.items == []
    assert cart.price == 0.0
