from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from shop_api import db
from shop_api.main import app

client = TestClient(app)


def test_missing_cart():
    response = client.get("/cart/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_cart():
    response = client.post("/cart/999999/add/1")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item():
    cart_id = client.post("/cart").json()["id"]
    response = client.post(f"/cart/{cart_id}/add/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_deleted_item():
    item = client.post("/item", json={"name": "gone", "price": 4}).json()
    client.delete(f"/item/{item['id']}")
    cart_id = client.post("/cart").json()["id"]
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_same_item_twice():
    item = client.post("/item", json={"name": "twice", "price": 2.5}).json()
    cart_id = client.post("/cart").json()["id"]
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["items"][0]["quantity"] == 2


def test_deleted_item_stays_in_cart():
    item = client.post("/item", json={"name": "paper", "price": 3}).json()
    cart_id = client.post("/cart").json()["id"]
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    client.delete(f"/item/{item['id']}")
    body = client.get(f"/cart/{cart_id}").json()
    assert body["items"][0]["available"] is False
    assert body["price"] == 3


def test_item_list_skips_cheap_and_deleted():
    cheap = client.post("/item", json={"name": "cheap", "price": 1}).json()
    client.delete(f"/item/{cheap['id']}")
    listed = client.get("/item", params={"min_price": 1000, "limit": 50}).json()
    assert all(row["price"] >= 1000 for row in listed)
    shown = client.get("/item", params={"limit": 50}).json()
    assert all(row["id"] != cheap["id"] for row in shown)


def test_missing_item_routes():
    assert client.get("/item/999999").status_code == HTTPStatus.NOT_FOUND
    assert client.put("/item/999999", json={"name": "n", "price": 1}).status_code == HTTPStatus.NOT_FOUND
    assert client.patch("/item/999999", json={"name": "n"}).status_code == HTTPStatus.NOT_FOUND
    assert client.delete("/item/999999").status_code == HTTPStatus.NOT_FOUND


def test_chat_rooms():
    with client.websocket_connect("/chat/kitchen") as a, client.websocket_connect("/chat/kitchen") as b:
        a.send_text("привет")
        first = b.receive_text()
        assert first.endswith(" :: привет")
        b.send_text("ок")
        second = a.receive_text()
        assert second.endswith(" :: ок")
        assert first.split(" :: ")[0] != second.split(" :: ")[0]

    with client.websocket_connect("/chat/kitchen") as again, client.websocket_connect("/chat/yard") as other:
        other.send_text("мимо")
        again.send_text("ещё")
        other.send_text("ещё раз")


def test_make_engine_both(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    sqlite_engine = db.make_engine()
    sqlite_engine.dispose()

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:password@127.0.0.1:1/shop")
    pg_engine = db.make_engine()
    pg_engine.dispose()


def test_init_db_retries(monkeypatch):
    orig = db.Base.metadata.create_all
    state = {"n": 0}

    def fake(*args, **kwargs):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("db down")
        return orig(*args, **kwargs)

    monkeypatch.setattr(db.Base.metadata, "create_all", fake)
    monkeypatch.setattr(db.time, "sleep", lambda *_: None)
    db.init_db()
    assert state["n"] == 2


def test_init_db_gives_up(monkeypatch):
    def fake(*args, **kwargs):
        raise RuntimeError("still down")

    monkeypatch.setattr(db.Base.metadata, "create_all", fake)
    monkeypatch.setattr(db.time, "sleep", lambda *_: None)
    with pytest.raises(RuntimeError):
        db.init_db()
