import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from shop_api.main import app

client = TestClient(app)


@pytest.fixture()
def cart_id():
    return client.post("/cart").json()["id"]


@pytest.fixture()
def item_id():
    return client.post("/item", json={"name": "test", "price": 10.0}).json()["id"]


def test_post_cart_location_header():
    resp = client.post("/cart")
    assert resp.status_code == 201
    assert resp.headers["Location"] == f"/cart/{resp.json()['id']}"


def test_get_cart_not_found():
    resp = client.get("/cart/999999")
    assert resp.status_code == 404


def test_create_item_location_header():
    resp = client.post("/item", json={"name": "loc_test", "price": 5.0})
    assert resp.status_code == 201
    assert resp.headers["Location"] == "/item/" + str(resp.json()["id"])


def test_get_item_deleted_returns_404():
    item_resp = client.post("/item", json={"name": "to_delete", "price": 1.0})
    item_id = item_resp.json()["id"]
    client.delete(f"/item/{item_id}")
    resp = client.get(f"/item/{item_id}")
    assert resp.status_code == 404


def test_get_items_with_show_deleted():
    client.post("/item", json={"name": "del", "price": 1.0})
    resp = client.get("/item", params={"show_deleted": "true"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_patch_item_item_404():
    resp = client.patch(
        "/item/999999",
        json={"name": "x"},
    )
    assert resp.status_code == 404


def test_delete_item_returns_success(cart_id, item_id):
    client.post(f"/cart/{cart_id}/add/{item_id}")
    resp = client.delete(f"/item/{item_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_update_item_item_404():
    resp = client.put("/item/999999", json={"name": "x", "price": 0})
    assert resp.status_code == 404


def test_add_item_item_404(cart_id):
    resp = client.post(f"/cart/{cart_id}/add/999999")
    assert resp.status_code == 404
