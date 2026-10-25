"""Дополнительные тесты ДЗ5: ветки «не найдено» и служебные модули.

Отдельный файл, чтобы не смешивать их с тестами из задания (test_homework2.py).
"""

import runpy
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from shop_api import store
from shop_api.main import app
from shop_api.store.models import CartEntity, CartItem

client = TestClient(app)

# заведомо не существующий идентификатор (максимум для Integer в PostgreSQL)
MISSING_ID = 2**31 - 1


@pytest.fixture()
def item() -> dict[str, Any]:
    return client.post("/item", json={"name": "coverage item", "price": 10.0}).json()


@pytest.fixture()
def cart_id() -> int:
    return client.post("/cart").json()["id"]


def test_get_missing_cart_returns_404() -> None:
    response = client.get(f"/cart/{MISSING_ID}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_missing_cart_returns_404(item: dict[str, Any]) -> None:
    response = client.post(f"/cart/{MISSING_ID}/add/{item['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item_to_cart_returns_404(cart_id: int) -> None:
    response = client.post(f"/cart/{cart_id}/add/{MISSING_ID}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_missing_item_returns_404() -> None:
    response = client.put(f"/item/{MISSING_ID}", json={"name": "x", "price": 1.0})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_deleted_item_returns_404(item: dict[str, Any]) -> None:
    client.delete(f"/item/{item['id']}")

    response = client.put(f"/item/{item['id']}", json={"name": "x", "price": 1.0})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_store_returns_none_for_missing_entities() -> None:
    assert store.get_cart(MISSING_ID) is None
    assert store.get_item(MISSING_ID) is None
    assert store.update_item(MISSING_ID, store.ItemInfo(name="x", price=1.0)) is None
    assert store.add_item_to_cart(MISSING_ID, MISSING_ID) is None


def test_adding_same_item_twice_increases_quantity(
    cart_id: int,
    item: dict[str, Any],
) -> None:
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")

    [position] = response.json()["items"]
    assert position["quantity"] == 2
    assert response.json()["price"] == pytest.approx(20.0)


def test_cart_entity_quantity_sums_positions() -> None:
    entity = CartEntity(
        id=1,
        items=[
            CartItem(id=1, name="a", quantity=2, available=True),
            CartItem(id=2, name="b", quantity=3, available=True),
        ],
        price=0.0,
    )

    assert entity.quantity == 5


def test_isolation_main_prints_every_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    from isolation.scenarios import SCENARIOS

    runpy.run_module("isolation", run_name="__main__")

    output = capsys.readouterr().out
    assert all(title in output for title, *_ in SCENARIOS)
