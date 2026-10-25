from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from shop_api import main


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """
    Создание тестового клиента с отдельными хранилищами товаров и корзин
    """

    monkeypatch.setattr(main, "items", {})
    monkeypatch.setattr(main, "carts", {})

    with TestClient(main.app) as client:
        yield client


@pytest.fixture()
def item(client: TestClient) -> dict[str, Any]:
    """
    Создание товара для теста
    """

    response = client.post("/item", json={"name": "Монки Ди Луффи", "price": 10.0})
    assert response.status_code == 201

    return response.json()


@pytest.fixture()
def cart_id(client: TestClient) -> int:
    """
    Создание пустой корзины для теста
    """

    response = client.post("/cart")
    assert response.status_code == 201

    return response.json()["id"]


def test_create_and_fetch_empty_cart(client: TestClient) -> None:
    """
    Создание пустых корзин с разными идентификаторами и получение по ссылке
    """

    for expected_id in (1, 2):
        response = client.post("/cart")

        assert response.status_code == 201
        assert response.json() == {"id": expected_id}
        assert response.headers["location"] == f"/cart/{expected_id}"

        response = client.get(response.headers["location"])

        assert response.status_code == 200
        assert response.json() == {"id": expected_id, "items": [], "price": 0.0}


def test_create_and_fetch_item(client: TestClient) -> None:
    """
    Создание товаров с нулевой ценой и получение по ссылке
    """

    for expected_id in (1, 2):
        response = client.post("/item", json={"name": "Ророноа Зоро", "price": 0})

        assert response.status_code == 201
        assert response.headers["location"] == f"/item/{expected_id}"
        expected_item = {
            "id": expected_id,
            "name": "Ророноа Зоро",
            "price": 0.0,
            "deleted": False
        }
        assert response.json() == expected_item

        response = client.get(response.headers["location"])

        assert response.status_code == 200
        assert response.json() == expected_item


@pytest.mark.parametrize(
    ("method", "path", "body", "error"),
    [
        ("GET", "/cart/999", None, "Cart not found"),
        ("GET", "/item/999", None, "Item not found"),
        ("POST", "/cart/999/add/1", None, "Cart not found"),
        ("POST", "/cart/1/add/999", None, "Item not found"),
        ("PUT", "/item/999", {"name": "Усопп", "price": 1}, "Item not found"),
        ("PATCH", "/item/999", {"price": 1}, "Item not found"),
    ],
)
def test_missing_resource(
    client: TestClient,
    cart_id: int,
    item: dict[str, Any],
    method: str,
    path: str,
    body: dict[str, Any] | None,
    error: str,
) -> None:
    """
    Проверка ошибки при обращении к несуществующей корзине или товару
    """

    response = client.request(method, path, json=body)

    assert response.status_code == 404
    assert response.json() == {"error": error}
    assert client.get("/item").json() == [item]


def test_repeated_addition_and_deleted_item_in_cart(
    client: TestClient,
    cart_id: int,
    item: dict[str, Any],
) -> None:
    """
    Повторное добавление товара и пересчёт корзины после его удаления
    """

    item_id = item["id"]
    response = client.post("/item", json={"name": "Санджи", "price": 2.5})
    other_item = response.json()
    other_item_id = other_item["id"]

    for quantity in (1, 2):
        response = client.post(f"/cart/{cart_id}/add/{item_id}")

        assert response.status_code == 200
        assert response.json() == {
            "id": cart_id,
            "items": [{
                "id": item_id,
                "name": item["name"],
                "quantity": quantity,
                "available": True
            }],
            "price": item["price"] * quantity
        }

    response = client.post(f"/cart/{cart_id}/add/{other_item_id}")
    assert response.status_code == 200

    response = client.delete(f"/item/{item_id}")
    assert response.status_code == 200

    expected_cart = {
        "id": cart_id,
        "items": [
            {
                "id": item_id,
                "name": item["name"],
                "quantity": 2,
                "available": False
            },
            {
                "id": other_item_id,
                "name": other_item["name"],
                "quantity": 1,
                "available": True
            }
        ],
        "price": 2.5
    }
    response = client.get(f"/cart/{cart_id}")
    assert response.json() == expected_cart

    response = client.post(f"/cart/{cart_id}/add/{item_id}")

    assert response.status_code == 404
    assert response.json() == {"error": "Item not found"}

    response = client.get("/cart", params={"min_quantity": 3, "max_quantity": 3})
    assert response.json() == [expected_cart]


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({}, [1, 2, 3, 4]),
        ({"min_price": 10}, [2, 3, 4]),
        ({"max_price": 20}, [1, 2, 3]),
        ({"min_quantity": 1}, [2, 3, 4]),
        ({"max_quantity": 2}, [1, 2, 3]),
        ({"min_price": 10, "max_price": 20, "min_quantity": 1, "max_quantity": 2}, [2, 3]),
        ({"offset": 1, "limit": 2}, [2, 3]),
        ({"min_price": 10, "offset": 1, "limit": 1}, [3]),
        ({"max_price": 0, "max_quantity": 0}, [1]),
        ({"min_price": 31}, []),
        ({"min_quantity": 4}, []),
        ({"offset": 4}, []),
    ],
)
def test_cart_filters_and_pagination(
    client: TestClient,
    item: dict[str, Any],
    params: dict[str, Any],
    expected_ids: list[int],
) -> None:
    """
    Фильтрация корзин по стоимости и количеству товаров с пагинацией
    """

    item_id = item["id"]

    for quantity in range(4):
        cart_id = client.post("/cart").json()["id"]

        for _ in range(quantity):
            response = client.post(f"/cart/{cart_id}/add/{item_id}")
            assert response.status_code == 200

    response = client.get("/cart", params=params)

    assert response.status_code == 200
    assert [cart["id"] for cart in response.json()] == expected_ids


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({}, [1, 2, 4]),
        ({"min_price": 10}, [2, 4]),
        ({"max_price": 20}, [1, 2]),
        ({"min_price": 10, "max_price": 10}, [2]),
        ({"offset": 1, "limit": 1}, [2]),
        ({"min_price": 10, "offset": 1, "limit": 1}, [4]),
        ({"show_deleted": True}, [1, 2, 3, 4]),
        ({"show_deleted": False}, [1, 2, 4]),
        ({"show_deleted": True, "min_price": 20, "max_price": 20}, [3]),
        ({"min_price": 31}, []),
        ({"offset": 4}, []),
    ],
)
def test_item_filters_and_pagination(
    client: TestClient,
    params: dict[str, Any],
    expected_ids: list[int],
) -> None:
    """
    Фильтрация товаров по цене и признаку удаления с пагинацией
    """

    for name, price in (("Чоппер", 0), ("Нико Робин", 10), ("Фрэнки", 20), ("Брук", 30)):
        response = client.post("/item", json={"name": name, "price": price})
        assert response.status_code == 201

    response = client.delete("/item/3")
    assert response.status_code == 200

    response = client.get("/item", params=params)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == expected_ids


@pytest.mark.parametrize("path", ["/item", "/cart"])
def test_empty_lists_and_default_limit(client: TestClient, path: str) -> None:
    """
    Получение пустого списка и ограничение количества записей по умолчанию
    """

    assert client.get(path).json() == []

    for _ in range(12):
        body = {"name": "Усопп", "price": 1} if path == "/item" else None
        response = client.post(path, json=body)
        assert response.status_code == 201

    response = client.get(path)

    assert response.status_code == 200
    assert [entry["id"] for entry in response.json()] == list(range(1, 11))

    response = client.get(path, params={"offset": 10})
    assert [entry["id"] for entry in response.json()] == [11, 12]


@pytest.mark.parametrize("path", ["/item", "/cart"])
@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"offset": "abc"},
        {"limit": 0},
        {"limit": -1},
        {"min_price": -1},
        {"max_price": -1},
        {"min_price": "nan"},
        {"max_price": "inf"},
    ],
)
def test_invalid_list_query(
    client: TestClient,
    path: str,
    params: dict[str, Any],
) -> None:
    """
    Отклонение некорректных параметров списка товаров или корзин
    """

    response = client.get(path, params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"min_quantity": -1},
        {"max_quantity": -1},
        {"min_quantity": 1.5},
    ],
)
def test_invalid_cart_quantity_query(client: TestClient, params: dict[str, Any]) -> None:
    """
    Отклонение некорректного количества товаров в фильтре корзин
    """

    response = client.get("/cart", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH"])
@pytest.mark.parametrize(
    "body",
    [
        {"name": "Усопп", "price": -1},
        {"name": "Усопп", "price": None},
        {"name": None, "price": 1},
        {"name": "Усопп", "price": "nan"},
        {"name": "Усопп", "price": "inf"},
        {"name": "Усопп", "price": 1, "deleted": True},
        {"name": "Усопп", "price": 1, "unknown": "value"},
    ],
)
def test_invalid_item_body_does_not_change_items(
    client: TestClient,
    item: dict[str, Any],
    method: str,
    body: dict[str, Any],
) -> None:
    """
    Отклонение некорректных данных товара без изменения хранилища
    """

    item_id = item["id"]
    path = "/item" if method == "POST" else f"/item/{item_id}"
    response = client.request(method, path, json=body)

    assert response.status_code == 422
    assert client.get("/item").json() == [item]


@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize("body", [{}, {"name": "Усопп"}, {"price": 1}])
def test_required_item_fields(
    client: TestClient,
    item: dict[str, Any],
    method: str,
    body: dict[str, Any],
) -> None:
    """
    Проверка обязательных полей при создании и полной замене товара
    """

    item_id = item["id"]
    path = "/item" if method == "POST" else f"/item/{item_id}"
    response = client.request(method, path, json=body)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("PUT", {"name": "Нами", "price": 0}),
        ("PATCH", {"name": "Нами"}),
        ("PATCH", {"price": 0}),
        ("PATCH", {"name": "Нами", "price": 2.5}),
        ("PATCH", {}),
    ],
)
def test_update_item_and_cart(
    client: TestClient,
    item: dict[str, Any],
    cart_id: int,
    method: str,
    body: dict[str, Any],
) -> None:
    """
    Обновление товара и отображение новых данных в корзине
    """

    item_id = item["id"]
    response = client.post(f"/cart/{cart_id}/add/{item_id}")
    assert response.status_code == 200

    expected_item = item.copy()
    expected_item.update(body)
    response = client.request(method, f"/item/{item_id}", json=body)

    assert response.status_code == 200
    assert response.json() == expected_item
    assert client.get(f"/item/{item_id}").json() == expected_item

    response = client.get(f"/cart/{cart_id}")

    assert response.json() == {
        "id": cart_id,
        "items": [{
            "id": item_id,
            "name": expected_item["name"],
            "quantity": 1,
            "available": True
        }],
        "price": expected_item["price"]
    }


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_deleted_item_cannot_be_updated(
    client: TestClient,
    item: dict[str, Any],
    method: str,
) -> None:
    """
    Запрет обновления удалённого товара
    """

    item_id = item["id"]
    path = f"/item/{item_id}"
    response = client.delete(path)
    assert response.status_code == 200

    response = client.request(method, path, json={"name": "Шанкс", "price": 99})

    assert response.status_code == 304
    assert response.content == b""
    assert client.get(path).status_code == 404

    expected_item = item.copy()
    expected_item["deleted"] = True
    response = client.get("/item", params={"show_deleted": True})
    assert response.json() == [expected_item]


def test_delete_is_idempotent_and_does_not_create_items(
    client: TestClient,
    item: dict[str, Any],
) -> None:
    """
    Повторное удаление товара и удаление несуществующего товара
    """

    for item_id in (item["id"], item["id"], 999):
        response = client.delete(f"/item/{item_id}")

        assert response.status_code == 200
        assert response.json() == {}

    assert client.get("/item").json() == []

    expected_item = item.copy()
    expected_item["deleted"] = True
    response = client.get("/item", params={"show_deleted": True})
    assert response.json() == [expected_item]
