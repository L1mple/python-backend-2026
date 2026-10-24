from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from shop_api.main import app

client = TestClient(app)


# --- ITEMS: Негативные сценарии (404, 304) ---


def test_get_item_not_found() -> None:
    response = client.get("/item/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_item_not_found() -> None:
    response = client.put("/item/999999", json={"name": "x", "price": 10.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_item_not_found() -> None:
    response = client.delete("/item/999999")
    # В текущей реализации DELETE возвращает 200, даже если товара нет
    assert response.status_code == HTTPStatus.OK


def test_patch_item_not_found() -> None:
    response = client.patch("/item/999999", json={"name": "x"})
    assert response.status_code == HTTPStatus.NOT_MODIFIED


# --- ITEMS: Фильтры и удаленные ---


def test_get_items_with_show_deleted() -> None:
    item = client.post("/item", json={"name": "deleted", "price": 10.0}).json()
    client.delete(f"/item/{item['id']}")

    # По умолчанию удаленных нет
    response = client.get("/item", params={"limit": 100})
    assert all(i["id"] != item["id"] for i in response.json())

    # С флагом show_deleted=True — есть
    response = client.get("/item", params={"show_deleted": True, "limit": 100})
    assert any(i["id"] == item["id"] for i in response.json())


def test_get_items_filter_price() -> None:
    client.post("/item", json={"name": "cheap", "price": 5.0})
    client.post("/item", json={"name": "expensive", "price": 500.0})

    response = client.get("/item", params={"min_price": 100.0, "limit": 100})
    assert all(i["price"] >= 100.0 for i in response.json())

    response = client.get("/item", params={"max_price": 50.0, "limit": 100})
    assert all(i["price"] <= 50.0 for i in response.json())


# --- CARTS: Негативные сценарии ---


def test_get_cart_not_found() -> None:
    response = client.get("/cart/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_to_cart_not_found() -> None:
    # 1. Несуществующая корзина
    response = client.post("/cart/999999/add/1")
    assert response.status_code == HTTPStatus.NOT_FOUND

    cart_id = client.post("/cart").json()["id"]

    # 2. Существующая корзина, несуществующий товар
    response = client.post(f"/cart/{cart_id}/add/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND

    # 3. Существующая корзина, удаленный товар
    item = client.post("/item", json={"name": "del", "price": 10.0}).json()
    client.delete(f"/item/{item['id']}")
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


# --- CARTS: Фильтры и логика ---


def test_cart_filters() -> None:
    item1 = client.post("/item", json={"name": "i1", "price": 10.0}).json()
    item2 = client.post("/item", json={"name": "i2", "price": 100.0}).json()

    cart1 = client.post("/cart").json()["id"]
    cart2 = client.post("/cart").json()["id"]

    client.post(f"/cart/{cart1}/add/{item1['id']}")
    client.post(f"/cart/{cart2}/add/{item2['id']}")

    response = client.get("/cart", params={"min_price": 50.0, "limit": 100})
    assert all(c["price"] >= 50.0 for c in response.json())

    response = client.get("/cart", params={"max_price": 50.0, "limit": 100})
    assert all(c["price"] <= 50.0 for c in response.json())

    response = client.get("/cart", params={"min_quantity": 1, "limit": 100})
    assert all(
        sum(i["quantity"] for i in c["items"]) >= 1 for c in response.json()
    )

    response = client.get("/cart", params={"max_quantity": 0, "limit": 100})
    assert all(
        sum(i["quantity"] for i in c["items"]) <= 0 for c in response.json()
    )


def test_add_same_item_increments_quantity() -> None:
    item = client.post("/item", json={"name": "inc", "price": 10.0}).json()
    cart = client.post("/cart").json()["id"]

    client.post(f"/cart/{cart}/add/{item['id']}")
    client.post(f"/cart/{cart}/add/{item['id']}")

    response = client.get(f"/cart/{cart}")
    assert response.json()["items"][0]["quantity"] == 2


# --- MAIN: Покрытие lifespan ---


def test_lifespan() -> None:
    """Покрывает lifespan в main.py (он не вызывается, если TestClient создан без with)."""
    with TestClient(app) as test_client:
        response = test_client.get("/item")
        assert response.status_code == HTTPStatus.OK


# --- CARTS: товар, физически отсутствующий в БД ---


def test_cart_with_missing_item(monkeypatch) -> None:
    """
    Покрывает ветку `if item is None: continue` в carts/routes.py,
    когда корзина ссылается на товар, которого нет в БД.

    Физическое удаление из `items` в PostgreSQL запрещено из-за FK
    на `cart_items`, поэтому подменяем `get_item_raw` через monkeypatch.
    """
    from shop_api.api.carts import routes as carts_routes

    cart_id = client.post("/cart").json()["id"]
    item = client.post("/item", json={"name": "missing", "price": 10.0}).json()
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    original = carts_routes.get_item_raw

    async def fake_get_item_raw(item_id: int):
        if item_id == item["id"]:
            return None
        return await original(item_id)

    monkeypatch.setattr(carts_routes, "get_item_raw", fake_get_item_raw)

    response = client.get(f"/cart/{cart_id}")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()["items"]) == 0
