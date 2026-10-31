"""Доп. тесты для достижения 95% покрытия shop_api.main."""
from http import HTTPStatus

from fastapi.testclient import TestClient

from shop_api.main import app, items

client = TestClient(app)


def test_get_nonexistent_item_returns_404() -> None:
    response = client.get("/item/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_nonexistent_cart_returns_404() -> None:
    response = client.get("/cart/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_to_nonexistent_cart_returns_404() -> None:
    item = client.post("/item", json={"name": "x", "price": 1.0}).json()
    response = client.post(f"/cart/999999/add/{item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_nonexistent_item_returns_404() -> None:
    cart_id = client.post("/cart").json()["id"]
    response = client.post(f"/cart/{cart_id}/add/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_nonexistent_item_returns_404() -> None:
    response = client.put("/item/999999", json={"name": "x", "price": 1.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_nonexistent_item_returns_404() -> None:
    response = client.patch("/item/999999", json={"price": 1.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_nonexistent_item_returns_404() -> None:
    response = client.delete("/item/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_deleted_item_returns_404() -> None:
    item = client.post("/item", json={"name": "x", "price": 1.0}).json()
    client.delete(f"/item/{item['id']}")
    response = client.get(f"/item/{item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_items_excludes_deleted_by_default() -> None:
    item = client.post("/item", json={"name": "x", "price": 1.0}).json()
    client.delete(f"/item/{item['id']}")

    default = client.get("/item", params={"limit": 1000}).json()
    assert all(i["id"] != item["id"] for i in default)

    with_deleted = client.get(
        "/item", params={"limit": 1000, "show_deleted": True}
    ).json()
    assert any(i["id"] == item["id"] for i in with_deleted)


def test_add_to_cart_increments_quantity() -> None:
    item = client.post("/item", json={"name": "x", "price": 2.0}).json()
    cart_id = client.post("/cart").json()["id"]

    client.post(f"/cart/{cart_id}/add/{item['id']}")
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["quantity"] == 2
    assert cart["price"] == 4.0


def test_cart_with_orphan_item() -> None:
    """Покрывает защитную ветку cart_to_dict: item_id в корзине есть,
    а самого товара в items нет. Через public API недостижимо, но
    ветку `continue` надо покрыть."""
    item = client.post("/item", json={"name": "x", "price": 1.0}).json()
    cart_id = client.post("/cart").json()["id"]
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    orphan = items.pop(item["id"])
    try:
        cart = client.get(f"/cart/{cart_id}").json()
        assert cart["items"] == []
        assert cart["price"] == 0.0
    finally:
        items[item["id"]] = orphan
