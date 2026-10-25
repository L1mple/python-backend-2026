# hw2/hw/test_coverage.py

from http import HTTPStatus
import pytest
from fastapi.testclient import TestClient

from shop_api.database import init_db, get_session
from shop_api.main import app, lifespan
from shop_api.models import CartItem

client = TestClient(app)


# ==========================================
# 1. Edge Cases & 404 Error Handling
# ==========================================

def test_get_cart_not_found():
    response = client.get("/cart/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "Cart not found"


def test_add_to_cart_not_found_cart():
    # Создаем существующий товар, но корзину передаем заведомо несуществующую
    item_resp = client.post("/item", json={"name": "Temp Item", "price": 50.0})
    item_id = item_resp.json()["id"]

    response = client.post(f"/cart/999999/add/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "Cart not found"


def test_add_to_cart_not_found_item():
    cart_resp = client.post("/cart")
    cart_id = cart_resp.json()["id"]

    response = client.post(f"/cart/{cart_id}/add/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "Item not found"


def test_put_item_not_found():
    response = client.put("/item/999999", json={"name": "Ghost", "price": 10.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_item_already_deleted():
    item_resp = client.post("/item", json={"name": "To be deleted", "price": 10.0})
    item_id = item_resp.json()["id"]
    client.delete(f"/item/{item_id}")

    # PUT на удаленный товар должен отдавать 404 (согласно фильтру Item.deleted == False)
    response = client.put(f"/item/{item_id}", json={"name": "Revived", "price": 20.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_item_not_found():
    response = client.patch("/item/999999", json={"price": 10.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_item_not_found():
    response = client.delete("/item/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


# ==========================================
# 2. Бизнес-логика корзины (Business Logic)
# ==========================================

def test_add_item_increment_quantity():
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "Apple", "price": 100.0}).json()["id"]

    # Первое добавление
    res1 = client.post(f"/cart/{cart_id}/add/{item_id}")
    assert res1.status_code == HTTPStatus.OK

    # Повторное добавление — проверяем инкремент (quantity += 1)
    res2 = client.post(f"/cart/{cart_id}/add/{item_id}")
    assert res2.status_code == HTTPStatus.OK

    cart = client.get(f"/cart/{cart_id}").json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 2
    assert cart["price"] == 200.0


def test_cart_ignores_deleted_items():
    """Если товар удален (soft delete), он не должен попадать в расчет корзины."""
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "Orange", "price": 50.0}).json()["id"]

    client.post(f"/cart/{cart_id}/add/{item_id}")

    # Мягко удаляем сам товар
    client.delete(f"/item/{item_id}")

    # Корзина должна стать пустой с ценой 0.0
    cart = client.get(f"/cart/{cart_id}").json()
    assert len(cart["items"]) == 0
    assert cart["price"] == 0.0


def test_get_carts_all_filters():
    """Тестируем ветки отсечения фильтров min/max price и quantity."""
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "Filter Item", "price": 100.0}).json()["id"]
    client.post(f"/cart/{cart_id}/add/{item_id}")

    # min_price отсекает корзины дешевле 1000
    res = client.get("/cart", params={"min_price": 1000.0})
    assert all(c["price"] >= 1000.0 for c in res.json())

    # max_price отсекает корзины дороже 10
    res = client.get("/cart", params={"max_price": 10.0})
    assert all(c["price"] <= 10.0 for c in res.json())

    # min_quantity отсекает корзины с малым числом товаров
    res = client.get("/cart", params={"min_quantity": 500})
    assert len(res.json()) == 0

    # max_quantity
    res = client.get("/cart", params={"max_quantity": 0})
    for c in res.json():
        assert sum(i["quantity"] for i in c["items"]) == 0


# ==========================================
# 3. Database Layer & Lifespan
# ==========================================

@pytest.mark.asyncio
async def test_init_db_and_lifespan():
    """Покрываем асинхронный init_db и lifespan приложения."""
    # Прямой вызов init_db
    await init_db()

    # Проверка работы контекстного менеджера lifespan
    async with lifespan(app):
        pass


@pytest.mark.asyncio
async def test_get_session():
    """Проверяем генератор сессий get_session."""
    async for session in get_session():
        assert session is not None
        assert session.is_active
        break


def test_models_representation():
    """Простая проверка инстанцирования модели связи."""
    link = CartItem(cart_id=1, item_id=2, quantity=5)
    assert link.cart_id == 1
    assert link.item_id == 2
    assert link.quantity == 5