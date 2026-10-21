import pytest
from fastapi.testclient import TestClient

from hw.shop_api.main import app, carts_db, items_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    items_db.clear()
    carts_db.clear()


def create_item(name="milk", price=100.0):
    return client.post("/item", json={"name": name, "price": price}).json()


def create_cart():
    return client.post("/cart").json()["id"]


def test_create_cart():
    response = client.post("/cart")

    assert response.status_code == 201
    assert response.headers["location"] == f"/cart/{response.json()['id']}"


def test_get_empty_cart():
    cart_id = create_cart()

    response = client.get(f"/cart/{cart_id}")

    assert response.status_code == 200
    assert response.json() == {"id": cart_id, "items": [], "price": 0.0}


def test_get_cart_not_found():
    response = client.get("/cart/999")

    assert response.status_code == 404


def test_add_item_to_cart_twice():
    item = create_item(price=100.0)
    cart_id = create_cart()

    client.post(f"/cart/{cart_id}/add/{item['id']}")
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")

    assert response.status_code == 200
    assert response.json()["price"] == 200.0
    assert response.json()["items"] == [
        {"id": item["id"], "name": "milk", "quantity": 2, "available": True}
    ]


def test_add_item_to_missing_cart():
    item = create_item()

    response = client.post(f"/cart/999/add/{item['id']}")

    assert response.status_code == 404


def test_add_missing_item_to_cart():
    cart_id = create_cart()

    response = client.post(f"/cart/{cart_id}/add/999")

    assert response.status_code == 404


def test_deleted_item_is_not_available_in_cart():
    item = create_item()
    cart_id = create_cart()
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    client.delete(f"/item/{item['id']}")
    response = client.get(f"/cart/{cart_id}")

    assert response.json()["items"][0]["available"] is False


def test_get_cart_list_with_filters():
    item = create_item(price=100.0)
    create_cart()
    cart_with_one = create_cart()
    cart_with_two = create_cart()
    client.post(f"/cart/{cart_with_one}/add/{item['id']}")
    client.post(f"/cart/{cart_with_two}/add/{item['id']}")
    client.post(f"/cart/{cart_with_two}/add/{item['id']}")

    assert len(client.get("/cart").json()) == 3
    assert len(client.get("/cart", params={"limit": 1}).json()) == 1
    assert len(client.get("/cart", params={"offset": 2}).json()) == 1
    assert len(client.get("/cart", params={"min_price": 100}).json()) == 2
    assert len(client.get("/cart", params={"max_price": 100}).json()) == 2
    assert len(client.get("/cart", params={"min_quantity": 2}).json()) == 1
    assert len(client.get("/cart", params={"max_quantity": 1}).json()) == 2


def test_get_cart_list_wrong_params():
    assert client.get("/cart", params={"offset": -1}).status_code == 422
    assert client.get("/cart", params={"limit": 0}).status_code == 422
    assert client.get("/cart", params={"min_price": -1}).status_code == 422
    assert client.get("/cart", params={"max_quantity": -1}).status_code == 422


def test_create_item():
    response = client.post("/item", json={"name": "milk", "price": 99.9})

    assert response.status_code == 201
    assert response.json()["name"] == "milk"
    assert response.json()["price"] == 99.9
    assert response.json()["deleted"] is False


def test_get_item():
    item = create_item()

    response = client.get(f"/item/{item['id']}")

    assert response.status_code == 200
    assert response.json() == item


def test_get_item_not_found():
    assert client.get("/item/999").status_code == 404


def test_get_deleted_item_not_found():
    item = create_item()
    client.delete(f"/item/{item['id']}")

    assert client.get(f"/item/{item['id']}").status_code == 404


def test_get_item_list_with_filters():
    create_item("milk", 50.0)
    bread = create_item("bread", 150.0)
    create_item("cheese", 300.0)

    assert len(client.get("/item").json()) == 3
    assert len(client.get("/item", params={"limit": 1}).json()) == 1
    assert len(client.get("/item", params={"offset": 2}).json()) == 1
    assert len(client.get("/item", params={"min_price": 100}).json()) == 2
    assert len(client.get("/item", params={"max_price": 100}).json()) == 1

    client.delete(f"/item/{bread['id']}")

    assert len(client.get("/item").json()) == 2
    assert len(client.get("/item", params={"show_deleted": True}).json()) == 3


def test_get_item_list_wrong_params():
    assert client.get("/item", params={"offset": -1}).status_code == 422
    assert client.get("/item", params={"limit": 0}).status_code == 422
    assert client.get("/item", params={"min_price": -1}).status_code == 422
    assert client.get("/item", params={"max_price": -1}).status_code == 422


def test_put_item():
    item = create_item()

    response = client.put(f"/item/{item['id']}", json={"name": "bread", "price": 50.0})

    assert response.status_code == 200
    assert response.json() == {"id": item["id"], "name": "bread", "price": 50.0, "deleted": False}


def test_put_item_not_found():
    response = client.put("/item/999", json={"name": "bread", "price": 50.0})

    assert response.status_code == 404


def test_put_item_without_price():
    item = create_item()

    response = client.put(f"/item/{item['id']}", json={"name": "bread"})

    assert response.status_code == 422


def test_patch_item():
    item = create_item(name="milk", price=100.0)

    response = client.patch(f"/item/{item['id']}", json={"price": 50.0})

    assert response.status_code == 200
    assert response.json()["name"] == "milk"
    assert response.json()["price"] == 50.0


def test_patch_item_not_found():
    assert client.patch("/item/999", json={"price": 50.0}).status_code == 404


def test_patch_deleted_item():
    item = create_item()
    client.delete(f"/item/{item['id']}")

    response = client.patch(f"/item/{item['id']}", json={"price": 50.0})

    assert response.status_code == 304


def test_patch_item_with_deleted_field():
    item = create_item()

    response = client.patch(f"/item/{item['id']}", json={"deleted": True})

    assert response.status_code == 422


def test_delete_item():
    item = create_item()

    response = client.delete(f"/item/{item['id']}")

    assert response.status_code == 200
    assert client.get(f"/item/{item['id']}").status_code == 404


def test_delete_item_twice_and_missing():
    item = create_item()
    client.delete(f"/item/{item['id']}")

    assert client.delete(f"/item/{item['id']}").status_code == 200
    assert client.delete("/item/999").status_code == 200
