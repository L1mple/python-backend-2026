from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from shop_api.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def make_item(client: TestClient) -> Callable[..., dict[str, Any]]:
    """Создает товар через API и возвращает его тело ответа."""

    def factory(name: str = "Тестовый товар", price: float = 10.0) -> dict[str, Any]:
        response = client.post("/item", json={"name": name, "price": price})
        assert response.status_code == 201
        return response.json()

    return factory


@pytest.fixture()
def make_cart(client: TestClient) -> Callable[[], int]:
    """Создает пустую корзину и возвращает ее id."""

    def factory() -> int:
        response = client.post("/cart")
        assert response.status_code == 201
        return response.json()["id"]

    return factory
