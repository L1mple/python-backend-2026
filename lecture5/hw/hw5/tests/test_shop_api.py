from __future__ import annotations

from http import HTTPStatus

import pytest
from fastapi import HTTPException

from hw.shop_api import main


def create_item(client, name="Apple", price=2.5):
    response = client.post("/item", json={"name": name, "price": price})
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


def create_cart(client):
    response = client.post("/cart")
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


def test_cart_creation_location_and_missing_cart(client):
    cart = create_cart(client)

    assert cart == {"id": 1, "items": [], "price": 0}
    assert client.headers.get("location") is None
    created = client.post("/cart")
    assert created.headers["location"] == "/cart/2"
    assert client.get("/cart/1").json() == cart
    assert client.get("/cart/999").status_code == HTTPStatus.NOT_FOUND
    assert client.get("/cart").json() == [cart, {"id": 2, "items": [], "price": 0}]


def test_item_crud_and_locations(client):
    apple = create_item(client)
    banana = create_item(client, "Banana", 4)

    assert apple == {"id": 1, "name": "Apple", "price": 2.5, "deleted": False}
    assert client.get("/item/1").json() == apple
    assert client.get("/item/999").status_code == HTTPStatus.NOT_FOUND
    assert client.post("/item", json={"name": "Pear", "price": 1}).headers["location"] == "/item/3"

    replaced = client.put("/item/1", json={"name": "Green apple", "price": 3})
    assert replaced.status_code == HTTPStatus.OK
    assert replaced.json()["name"] == "Green apple"
    patched = client.patch("/item/1", json={"price": 3.5})
    assert patched.json() == {
        "id": 1, "name": "Green apple", "price": 3.5, "deleted": False
    }
    assert client.patch("/item/1", json={"name": "Red apple"}).json()["price"] == 3.5
    assert client.get("/item").json() == [
        {"id": 1, "name": "Red apple", "price": 3.5, "deleted": False},
        banana,
        {"id": 3, "name": "Pear", "price": 1.0, "deleted": False},
    ]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "Apple"},
        {"price": 1},
        {"name": "Apple", "price": 1, "extra": True},
        {"name": 1, "price": 1},
        {"name": "Apple", "price": "1"},
        {"name": "Apple", "price": True},
        {"name": "Apple", "price": -1},
    ],
)
def test_item_validation_rejects_invalid_bodies(client, body):
    assert client.post("/item", json=body).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_invalid_json_and_non_object_bodies(client):
    assert client.post("/item", content="{").status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.post("/item", json=["Apple", 1]).status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    create_item(client)
    assert client.patch("/item/1", json={}).status_code == HTTPStatus.OK
    assert client.patch("/item/1", json={"name": 7}).status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.patch("/item/1", json={"price": -0.1}).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_item_filters_pagination_and_soft_deletion(client):
    create_item(client, "Cheap", 1)
    create_item(client, "Middle", 5)
    create_item(client, "Expensive", 10)

    assert [item["name"] for item in client.get("/item?min_price=5").json()] == [
        "Middle", "Expensive"
    ]
    assert [item["name"] for item in client.get("/item?max_price=5").json()] == [
        "Cheap", "Middle"
    ]
    assert [item["name"] for item in client.get("/item?offset=1&limit=1").json()] == ["Middle"]
    assert client.get("/item?offset=-1").status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.get("/item?limit=0").status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.get("/item?min_price=-1").status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    assert client.delete("/item/2").status_code == HTTPStatus.OK
    assert client.delete("/item/2").status_code == HTTPStatus.OK
    assert client.delete("/item/999").status_code == HTTPStatus.OK
    assert client.get("/item/2").status_code == HTTPStatus.NOT_FOUND
    assert [item["name"] for item in client.get("/item").json()] == ["Cheap", "Expensive"]
    assert client.get("/item?show_deleted=true").json()[1]["deleted"] is True
    assert client.put("/item/2", json={"name": "Restored", "price": 2}).status_code == HTTPStatus.NOT_MODIFIED
    assert client.patch("/item/999", json={"price": 2}).status_code == HTTPStatus.NOT_MODIFIED


def test_cart_items_total_available_flag_and_missing_resources(client):
    cart = create_cart(client)
    item = create_item(client, "Book", 10)
    second_item = create_item(client, "Pen", 2)

    assert client.post("/cart/999/add/1").status_code == HTTPStatus.NOT_FOUND
    assert client.post(f"/cart/{cart['id']}/add/999").status_code == HTTPStatus.NOT_FOUND
    added = client.post(f"/cart/{cart['id']}/add/{item['id']}")
    assert added.json()["price"] == 10
    added = client.post(f"/cart/{cart['id']}/add/{item['id']}")
    assert added.json()["items"][0]["quantity"] == 2
    assert client.post(f"/cart/{cart['id']}/add/{second_item['id']}").json()["price"] == 22

    client.delete(f"/item/{item['id']}")
    cart_data = client.get(f"/cart/{cart['id']}").json()
    assert cart_data["price"] == 2
    assert cart_data["items"] == [
        {"id": item["id"], "name": "Book", "quantity": 2, "available": False},
        {"id": second_item["id"], "name": "Pen", "quantity": 1, "available": True},
    ]


def test_cart_filters_and_pagination(client):
    first, second, third = create_cart(client), create_cart(client), create_cart(client)
    item = create_item(client, price=3)
    for _ in range(2):
        client.post(f"/cart/{first['id']}/add/{item['id']}")
    client.post(f"/cart/{second['id']}/add/{item['id']}")
    assert [cart["id"] for cart in client.get("/cart?min_price=6").json()] == [first["id"]]
    assert [cart["id"] for cart in client.get("/cart?max_price=3").json()] == [
        second["id"], third["id"]
    ]
    assert [cart["id"] for cart in client.get("/cart?min_quantity=2").json()] == [first["id"]]
    assert [cart["id"] for cart in client.get("/cart?max_quantity=0").json()] == [third["id"]]
    assert [cart["id"] for cart in client.get("/cart?offset=1&limit=1").json()] == [second["id"]]
    assert client.get("/cart?offset=-1").status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.get("/cart?limit=0").status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.get("/cart?min_quantity=-1").status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_helpers_and_validation_branches(session):
    item = main.Item(id=7, name="Item", price=2.0, deleted=False)
    deleted = main.Item(id=8, name="Deleted", price=2.0, deleted=True)
    session.add_all([item, deleted])
    session.commit()
    cart = main.Cart(id=1)
    cart.items.append(main.CartItem(item=item, quantity=3))
    cart.items.append(main.CartItem(item=deleted, quantity=2))
    session.add(cart)
    session.commit()
    assert main.item_response(item) == {"id": 7, "name": "Item", "price": 2.0, "deleted": False}
    assert main.cart_response(cart) == {
        "id": 1,
        "items": [
            {"id": 7, "name": "Item", "quantity": 3, "available": True},
            {"id": 8, "name": "Deleted", "quantity": 2, "available": False},
        ],
        "price": 6.0,
    }
    assert main.get_item_or_404(session, 7) is item
    assert main.get_cart_or_404(session, 1) is cart
    with pytest.raises(HTTPException) as item_error:
        main.get_item_or_404(session, 8)
    assert item_error.value.status_code == HTTPStatus.NOT_FOUND
    with pytest.raises(HTTPException):
        main.get_item_or_404(session, 99)
    with pytest.raises(HTTPException):
        main.get_cart_or_404(session, 99)
    assert main.validate_item_body({"name": "Name", "price": 1}) == ("Name", 1.0)
    assert main.validate_item_body({"name": "Name"}, partial=True) == ("Name", None)
    assert main.validate_item_body({"price": 1}, partial=True) == (None, 1.0)
    with pytest.raises(HTTPException):
        main.validate_item_body({"name": "Name"}, partial=False)


def test_websocket_broadcast_and_disconnect_cleanup(client):
    with client.websocket_connect("/chat/general") as first:
        with client.websocket_connect("/chat/general") as second:
            first.send_text("hello")
            assert second.receive_text() == "user-1 :: hello"
            second.send_text("reply")
            assert first.receive_text() == "user-2 :: reply"
        assert "general" in main.chat_clients
    assert "general" not in main.chat_clients
