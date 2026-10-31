from http import HTTPStatus

import pytest


def test_create_cart(client):
    response = client.post("/cart")

    assert response.status_code == HTTPStatus.CREATED
    cart_id = response.json()["id"]
    assert isinstance(cart_id, int)
    assert cart_id > 0
    assert response.headers["Location"] == f"/cart/{cart_id}"


def test_get_empty_cart(client, cart):
    response = client.get(f"/cart/{cart['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"id": cart["id"], "items": [], "price": 0.0}


def test_get_carts_empty(client):
    response = client.get("/cart")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


@pytest.mark.parametrize("quantity", [1, 3])
def test_add_item_to_cart(client, cart, item, add_to_cart, quantity):
    result = add_to_cart(cart["id"], item["id"], quantity)

    assert result == {
        "id": cart["id"],
        "items": [{
            "id": item["id"],
            "name": item["name"],
            "quantity": quantity,
            "available": True,
        }],
        "price": item["price"] * quantity,
    }
    assert client.get(f"/cart/{cart['id']}").json() == result


def test_cart_price_excludes_deleted_items(client, cart, create_item, add_to_cart):
    first = create_item(name="First", price=10)
    second = create_item(name="Second", price=25)
    add_to_cart(cart["id"], first["id"], quantity=2)
    result = add_to_cart(cart["id"], second["id"])
    assert result["price"] == 45

    client.delete(f"/item/{first['id']}")
    response = client.get(f"/cart/{cart['id']}")

    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result["price"] == 25
    assert result["items"][0] == {
        "id": first["id"], "name": "First", "quantity": 2, "available": False,
    }
    assert result["items"][1]["available"] is True
    assert client.get("/cart", params={"min_quantity": 3, "max_price": 25}).json() == [result]


def test_cart_reflects_item_changes(client, cart, item, add_to_cart):
    add_to_cart(cart["id"], item["id"], quantity=2)
    client.patch(f"/item/{item['id']}", json={"name": "Updated", "price": 7.5})

    response = client.get(f"/cart/{cart['id']}")

    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result["price"] == 15
    assert result["items"][0]["name"] == "Updated"
    assert client.get("/cart", params={"min_price": 15, "max_price": 15}).json() == [result]


@pytest.fixture()
def cart_catalog(create_cart, create_item, add_to_cart):
    item = create_item(price=10)
    carts = [create_cart() for _ in range(3)]
    add_to_cart(carts[1]["id"], item["id"])
    add_to_cart(carts[2]["id"], item["id"], quantity=3)
    return carts


@pytest.mark.parametrize(
    ("query", "indices"),
    [
        ({}, [0, 1, 2]),
        ({"min_price": 10}, [1, 2]),
        ({"max_price": 10}, [0, 1]),
        ({"min_price": 10, "max_price": 10}, [1]),
        ({"min_quantity": 2}, [2]),
        ({"max_quantity": 1}, [0, 1]),
        ({"min_quantity": 1, "max_quantity": 1}, [1]),
        ({"max_quantity": 0}, [0]),
        ({"min_price": 10, "max_quantity": 1}, [1]),
        ({"min_price": 100}, []),
        ({"offset": 1, "limit": 1}, [1]),
        ({"min_price": 10, "offset": 1, "limit": 1}, [2]),
    ],
)
def test_get_carts_filters_and_pagination(client, cart_catalog, query, indices):
    response = client.get("/cart", params=query)

    assert response.status_code == HTTPStatus.OK
    assert [cart["id"] for cart in response.json()] == [
        cart_catalog[index]["id"] for index in indices
    ]


def test_get_missing_cart(client):
    response = client.get("/cart/-1")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Cart not found"}


def test_add_to_missing_cart(client, item):
    response = client.post(f"/cart/-1/add/{item['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Cart not found"}


def test_add_missing_item_leaves_cart_empty(client, cart):
    response = client.post(f"/cart/{cart['id']}/add/-1")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Item not found"}
    assert client.get(f"/cart/{cart['id']}").json()["items"] == []


def test_add_deleted_item_leaves_cart_empty(client, cart, item):
    client.delete(f"/item/{item['id']}")

    response = client.post(f"/cart/{cart['id']}/add/{item['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert client.get(f"/cart/{cart['id']}").json() == {
        "id": cart["id"], "items": [], "price": 0.0,
    }


@pytest.mark.parametrize(
    "query",
    [
        {"offset": -1}, {"limit": 0},
        {"min_price": -1}, {"max_price": -1},
        {"min_quantity": -1}, {"max_quantity": -1},
    ],
)
def test_invalid_cart_query(client, query):
    response = client.get("/cart", params=query)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY