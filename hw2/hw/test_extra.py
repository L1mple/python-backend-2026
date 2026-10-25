from fastapi.testclient import TestClient
from shop_api.main import app
from shop_api.main import Cart, Item


client = TestClient(app)

def test_create_item_returns_sent_data():
    body = {"name": "Apple", "price": 50.0}

    response = client.post("/item", json=body)

    assert response.status_code == 201
    assert response.json()["name"] == body["name"]
    assert response.json()["price"] == body["price"]
    assert response.json()["deleted"] is False
    assert isinstance(response.json()["id"], int)


def test_get_item_quantity_returns_correct_quantity():
    cart = Cart(cart_id=1)
    cart.add_item(item_id=1, quantity=5)
    assert cart.get_item_quantity(item_id=1) == 5

def test_remove_item():
    cart = Cart(cart_id=1)
    cart.add_item(item_id=1, quantity=5)
    cart.remove_item(item_id=1, quantity=3)
    assert cart.get_item_quantity(item_id=1) == 2
    cart.remove_item(item_id=1, quantity=3)
    assert cart.get_item_quantity(item_id=1) == 0

def test_get_items():
    cart = Cart(cart_id=1)
    cart.add_item(item_id=1, quantity=5)
    cart.add_item(item_id=2, quantity=3)
    items = cart.get_items()
    assert len(items) == 2

def test_get_cart_httpexception():
    response = client.get("/cart/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Cart not found"}

def test_add_item_to_cart_httpexception():
    cart_response = client.post("/cart")
    cart_id = cart_response.json()["id"]
    item_response = client.post("/item", json={"name": "Test Item", "price": 10.0})
    item_id = item_response.json()["id"]

    client.delete(f"/item/{item_id}")

    response = client.post(f"/cart/{cart_id}/add/{item_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found or marked as deleted"}