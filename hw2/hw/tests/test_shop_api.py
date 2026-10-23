from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from shop_api import routes
from shop_api.main import app
from shop_api.store import store

client = TestClient(app)
MISSING_ID = 2_147_483_647


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", f"/cart/{MISSING_ID}", None),
        ("POST", f"/cart/{MISSING_ID}/add/{MISSING_ID}", None),
        (
            "PUT",
            f"/item/{MISSING_ID}",
            {"name": "missing", "price": 10.0},
        ),
        ("PATCH", f"/item/{MISSING_ID}", {}),
        ("DELETE", f"/item/{MISSING_ID}", None),
    ],
)
def test_missing_resources_return_not_found(
    method: str,
    path: str,
    body: dict | None,
) -> None:
    kwargs = {"json": body} if body is not None else {}

    response = client.request(method, path, **kwargs)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_patch_returns_not_found_if_item_disappears(monkeypatch) -> None:
    item = client.post(
        "/item",
        json={"name": "concurrently deleted", "price": 10.0},
    ).json()
    monkeypatch.setattr(routes.store, "patch_item", lambda *args, **kwargs: None)

    response = client.patch(f"/item/{item['id']}", json={"price": 20.0})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_store_does_not_patch_missing_or_deleted_item() -> None:
    assert store.patch_item(MISSING_ID, name="missing", price=None) is None

    item = store.create_item("deleted", 10.0)
    store.delete_item(item.id)

    result = store.patch_item(item.id, name="must not change", price=20.0)

    assert result is not None
    assert result.deleted is True
    assert result.name == "deleted"
    assert result.price == 10.0


def test_parallel_cart_updates_are_not_lost() -> None:
    item = store.create_item("parallel item", 10.0)
    cart_id = store.create_cart()
    additions = 12

    with ThreadPoolExecutor(max_workers=additions) as pool:
        results = list(
            pool.map(
                lambda _: store.add_to_cart(cart_id, item.id),
                range(additions),
            )
        )

    assert all(result is not None for result in results)
    cart = store.get_cart(cart_id)
    assert cart is not None
    assert len(cart.items) == 1
    assert cart.items[0].quantity == additions


@pytest.mark.asyncio
async def test_pause_emulates_slow_request(monkeypatch) -> None:
    sleep = AsyncMock()
    monkeypatch.setenv("LATENCY_EMULATION", "1")
    monkeypatch.setattr(routes.random, "random", lambda: 0.1)
    monkeypatch.setattr(routes.random, "uniform", lambda low, high: (low + high) / 2)
    monkeypatch.setattr(routes.asyncio, "sleep", sleep)

    await routes._pause(0.1, 0.2)

    sleep.assert_awaited_once()
    delay = sleep.await_args.args[0]
    assert delay == pytest.approx(0.55)
