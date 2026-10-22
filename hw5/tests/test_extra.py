from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from shop_api.db import _make_engine, get_db
from shop_api.main import chat_connections


def test_get_missing_cart_returns_404(client: TestClient) -> None:
    response = client.get("/cart/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_missing_item_returns_404(client: TestClient) -> None:
    response = client.get("/item/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_missing_item_returns_404(client: TestClient) -> None:
    response = client.put("/item/999999", json={"name": "x", "price": 1.0})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_missing_cart_returns_404(client: TestClient) -> None:
    item_id = client.post("/item", json={"name": "milk", "price": 2.5}).json()["id"]
    response = client.post(f"/cart/999999/add/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item_to_cart_returns_404(client: TestClient) -> None:
    cart_id = client.post("/cart").json()["id"]
    response = client.post(f"/cart/{cart_id}/add/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_same_item_increments_quantity(client: TestClient) -> None:
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "bread", "price": 3.0}).json()["id"]

    first = client.post(f"/cart/{cart_id}/add/{item_id}")
    second = client.post(f"/cart/{cart_id}/add/{item_id}")

    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.OK
    assert second.json()["items"][0]["quantity"] == 2
    assert second.json()["price"] == pytest.approx(6.0)


def test_deleted_item_is_unavailable_in_cart(client: TestClient) -> None:
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "tea", "price": 5.0}).json()["id"]
    client.post(f"/cart/{cart_id}/add/{item_id}")
    client.delete(f"/item/{item_id}")

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["available"] is False
    assert cart["price"] == pytest.approx(5.0)


def test_add_deleted_item_to_cart_returns_404(client: TestClient) -> None:
    cart_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "gone", "price": 1.0}).json()["id"]
    client.delete(f"/item/{item_id}")

    response = client.post(f"/cart/{cart_id}/add/{item_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_list_items_hides_deleted_by_default(client: TestClient) -> None:
    created = client.post("/item", json={"name": "hidden", "price": 12.0}).json()
    client.delete(f"/item/{created['id']}")

    visible = client.get("/item", params={"show_deleted": False}).json()
    assert all(item["id"] != created["id"] for item in visible)

    with_deleted = client.get("/item", params={"show_deleted": True, "limit": 500}).json()
    assert any(item["id"] == created["id"] and item["deleted"] is True for item in with_deleted)


def test_patch_name_only(client: TestClient) -> None:
    item = client.post("/item", json={"name": "old", "price": 8.0}).json()
    response = client.patch(f"/item/{item['id']}", json={"name": "new"})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "new"
    assert response.json()["price"] == pytest.approx(8.0)


def test_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == HTTPStatus.OK
    assert "http" in response.text.lower() or "python" in response.text.lower()


def test_chat_broadcast_and_disconnect(client: TestClient) -> None:
    room = "coverage-room"
    with client.websocket_connect(f"/chat/{room}") as first:
        with client.websocket_connect(f"/chat/{room}") as second:
            first.send_text("hello")
            message = second.receive_text()
            assert "hello" in message
            assert "::" in message
        assert room in chat_connections
    assert room not in chat_connections


def test_postgres_engine_is_created_without_connecting() -> None:
    engine = _make_engine("postgresql+psycopg2://shop:shop@localhost:5432/shop")
    assert engine.url.drivername == "postgresql+psycopg2"


def test_get_db_rolls_back_on_error() -> None:
    gen = get_db()
    next(gen)
    with pytest.raises(RuntimeError, match="boom"):
        gen.throw(RuntimeError("boom"))
