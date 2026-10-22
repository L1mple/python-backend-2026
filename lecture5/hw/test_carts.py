from http import HTTPStatus
import pytest


def test_create_cart(client):
    response = client.post("/cart")

    assert response.status_code == HTTPStatus.CREATED
    assert response.headers["location"] == f"/cart/{response.json()['id']}"


def test_get_empty_cart(client, cart_id):
    response = client.get(f"/cart/{cart_id}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"id": cart_id, "items": [], "price": 0.0}


def test_get_cart_not_found(client):
    assert client.get("/cart/999").status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_cart(client, cart_id, item):
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")

    assert response.status_code == HTTPStatus.OK
    cart = response.json()
    assert cart["items"] == [{"id": item["id"], "name": "Чай", "quantity": 2, "available": True}]
    assert cart["price"] == 300.0


def test_add_to_missing_cart(client, item):
    response = client.post(f"/cart/999/add/{item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_missing_item(client, cart_id):
    response = client.post(f"/cart/{cart_id}/add/999")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_deleted_item(client, cart_id, deleted_item):
    response = client.post(f"/cart/{cart_id}/add/{deleted_item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_item_not_available_after_delete(client, cart_id, item):
    client.post(f"/cart/{cart_id}/add/{item['id']}")
    client.delete(f"/item/{item['id']}")

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["available"] is False


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({}, [0, 1, 2]),
        ({"min_price": 50}, [1, 2]),
        ({"max_price": 100}, [0, 1]),
        ({"min_quantity": 2}, [2]),
        ({"max_quantity": 1}, [0, 1]),
        ({"offset": 1, "limit": 1}, [1]),
    ],
)
def test_get_carts_with_filters(client, items, params, expected):
    # корзины: пустая, одна за 50, две вещи за 100 + 200
    carts = []
    for indexes in [[], [0], [1, 3]]:
        cart_id = client.post("/cart").json()["id"]
        for i in indexes:
            client.post(f"/cart/{cart_id}/add/{items[i]['id']}")
        carts.append(cart_id)

    response = client.get("/cart", params=params)

    assert response.status_code == HTTPStatus.OK
    assert [c["id"] for c in response.json()] == [carts[i] for i in expected]


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"min_quantity": -1}])
def test_get_carts_bad_params(client, params):
    response = client.get("/cart", params=params)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
