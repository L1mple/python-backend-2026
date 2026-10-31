
from fastapi.testclient import TestClient

import store
from shop_api.main import app


client = TestClient(app)


def test_missing_item_in_store():
    missing_id = -999999

    assert store.get_one(missing_id) is None

    item_info = store.ItemInfo(
        name="Test",
        price=100,
    )
    assert store.update(missing_id, item_info) is None

    patch_info = store.PatchItemInfo(name="Updated")
    assert store.patch(missing_id, patch_info) is None

    store.delete(missing_id)


def test_missing_cart_in_store():
    missing_id = -999999

    assert store.get_cart(missing_id) is None
    assert store.add_item_to_cart(missing_id, 1) is False


def test_missing_cart_api():
    response = client.get("/cart/-999999")
    assert response.status_code == 404

    response = client.post("/cart/-999999/add/1")
    assert response.status_code == 404


def test_missing_item_in_cart_api():
    response = client.post("/cart")
    assert response.status_code == 201

    cart_id = response.json()["id"]

    response = client.post(
        f"/cart/{cart_id}/add/-999999"
    )
    assert response.status_code == 404


def test_store_price_filters():
    item = store.add(
        store.ItemInfo(
            name="Expensive test item",
            price=3000001,
        )
    )

    cheaper = store.get_many(
        max_price=3000000,
        limit=100000,
    )
    assert all(x.id != item.id for x in cheaper)

    more_expensive = store.get_many(
        min_price=3000002,
        limit=100000,
    )
    assert all(x.id != item.id for x in more_expensive)

    store.delete(item.id)

    active_items = store.get_many(limit=100000)
    assert all(x.id != item.id for x in active_items)
