from http import HTTPStatus

import pytest


def create_item(client, name="Book", price=10.0):
    response = client.post("/item", json={"name": name, "price": price})
    assert response.status_code == HTTPStatus.CREATED
    return response


def create_cart(client):
    response = client.post("/cart")
    assert response.status_code == HTTPStatus.CREATED
    return response


def test_create_and_get_item(client):
    response = create_item(client, "Python book", 19.99)
    assert response.headers["location"] == "/item/1"
    assert response.json() == {
        "id": 1,
        "name": "Python book",
        "price": 19.99,
        "deleted": False,
    }
    assert client.get("/item/1").json() == response.json()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "Book"},
        {"price": 10},
        {"name": "Book", "price": -1},
        {"name": "Book", "price": 10, "unexpected": True},
    ],
)
def test_create_item_validation(client, body):
    assert (
        client.post("/item", json=body).status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    )


def test_get_missing_and_deleted_item(client):
    assert client.get("/item/999").status_code == HTTPStatus.NOT_FOUND
    item_id = create_item(client).json()["id"]
    assert client.delete(f"/item/{item_id}").status_code == HTTPStatus.OK
    assert client.get(f"/item/{item_id}").status_code == HTTPStatus.NOT_FOUND


def test_item_filters_deleted_items_and_pagination(client):
    created = [
        create_item(client, "Free", 0).json(),
        create_item(client, "Book", 10).json(),
        create_item(client, "Course", 20).json(),
    ]
    client.delete("/item/2")

    assert client.get("/item").json() == [created[0], created[2]]
    deleted = {**created[1], "deleted": True}
    response = client.get(
        "/item",
        params={"min_price": 10, "max_price": 20, "show_deleted": True},
    )
    assert response.json() == [deleted, created[2]]
    assert client.get("/item", params={"max_price": 5}).json() == [created[0]]
    assert client.get("/item", params={"min_price": 30}).json() == []
    assert client.get("/item", params={"offset": 1, "limit": 1}).json() == [created[2]]


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": -1},
        {"min_price": -1},
        {"max_price": -1},
    ],
)
def test_item_filter_validation(client, params):
    assert (
        client.get("/item", params=params).status_code
        == HTTPStatus.UNPROCESSABLE_ENTITY
    )


def test_replace_item(client):
    item_id = create_item(client).json()["id"]
    response = client.put(f"/item/{item_id}", json={"name": "New book", "price": 25})
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": item_id,
        "name": "New book",
        "price": 25,
        "deleted": False,
    }


def test_replace_missing_or_deleted_item(client):
    body = {"name": "New book", "price": 25}
    assert client.put("/item/999", json=body).status_code == HTTPStatus.NOT_MODIFIED
    item_id = create_item(client).json()["id"]
    client.delete(f"/item/{item_id}")
    assert (
        client.put(f"/item/{item_id}", json=body).status_code == HTTPStatus.NOT_MODIFIED
    )


@pytest.mark.parametrize(
    ("patch", "expected_name", "expected_price"),
    [
        ({}, "Book", 10),
        ({"name": "New book"}, "New book", 10),
        ({"price": 25}, "Book", 25),
        ({"name": "New book", "price": 25}, "New book", 25),
    ],
)
def test_patch_item(client, patch, expected_name, expected_price):
    item_id = create_item(client).json()["id"]
    response = client.patch(f"/item/{item_id}", json=patch)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == expected_name
    assert response.json()["price"] == expected_price


@pytest.mark.parametrize(
    "patch",
    [
        {"name": None},
        {"price": None},
        {"price": -1},
        {"deleted": True},
    ],
)
def test_patch_validation_does_not_change_item(client, patch):
    item = create_item(client).json()
    assert (
        client.patch(f"/item/{item['id']}", json=patch).status_code
        == HTTPStatus.UNPROCESSABLE_ENTITY
    )
    assert client.get(f"/item/{item['id']}").json() == item


def test_patch_missing_or_deleted_item(client):
    assert (
        client.patch("/item/999", json={"price": 1}).status_code
        == HTTPStatus.NOT_MODIFIED
    )
    item_id = create_item(client).json()["id"]
    client.delete(f"/item/{item_id}")
    assert (
        client.patch(f"/item/{item_id}", json={"price": 1}).status_code
        == HTTPStatus.NOT_MODIFIED
    )


def test_delete_is_idempotent(client):
    item_id = create_item(client).json()["id"]
    assert client.delete(f"/item/{item_id}").status_code == HTTPStatus.OK
    assert client.delete(f"/item/{item_id}").status_code == HTTPStatus.OK
    assert client.delete("/item/999").status_code == HTTPStatus.OK


def test_create_and_get_empty_cart(client):
    response = create_cart(client)
    assert response.headers["location"] == "/cart/1"
    assert response.json() == {"id": 1}
    assert client.get("/cart/1").json() == {"id": 1, "items": [], "price": 0}


def test_get_missing_cart(client):
    assert client.get("/cart/999").status_code == HTTPStatus.NOT_FOUND


def test_add_item_to_cart_and_recalculate_current_item_data(client):
    item_id = create_item(client).json()["id"]
    cart_id = create_cart(client).json()["id"]
    path = f"/cart/{cart_id}/add/{item_id}"

    assert client.post(path).status_code == HTTPStatus.OK
    assert client.post(path).status_code == HTTPStatus.OK
    client.patch(f"/item/{item_id}", json={"name": "Updated", "price": 12.5})

    assert client.get(f"/cart/{cart_id}").json() == {
        "id": cart_id,
        "items": [{"id": item_id, "name": "Updated", "quantity": 2, "available": True}],
        "price": 25,
    }


def test_deleted_item_stays_in_cart_but_cannot_be_added_again(client):
    item_id = create_item(client, price=7).json()["id"]
    cart_id = create_cart(client).json()["id"]
    path = f"/cart/{cart_id}/add/{item_id}"
    client.post(path)
    client.delete(f"/item/{item_id}")

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["available"] is False
    assert cart["price"] == 7
    assert client.post(path).status_code == HTTPStatus.NOT_FOUND


def test_add_to_missing_cart_or_add_missing_item(client):
    assert client.post("/cart/999/add/999").status_code == HTTPStatus.NOT_FOUND
    cart_id = create_cart(client).json()["id"]
    assert client.post(f"/cart/{cart_id}/add/999").status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("params", "expected_indices"),
    [
        ({}, [0, 1, 2]),
        ({"min_price": 10}, [1, 2]),
        ({"max_price": 10}, [0, 1]),
        ({"min_quantity": 1}, [1, 2]),
        ({"max_quantity": 1}, [0, 1]),
        ({"min_price": 11}, [2]),
        ({"max_price": 9}, [0]),
        ({"min_quantity": 3}, []),
        ({"max_quantity": 0}, [0]),
        ({"offset": 1, "limit": 1}, [1]),
    ],
)
def test_cart_filters_and_pagination(client, params, expected_indices):
    item_id = create_item(client, price=10).json()["id"]
    cart_ids = [create_cart(client).json()["id"] for _ in range(3)]
    for index, cart_id in enumerate(cart_ids):
        for _ in range(index):
            client.post(f"/cart/{cart_id}/add/{item_id}")

    result = client.get("/cart", params=params)
    assert result.status_code == HTTPStatus.OK
    assert [cart["id"] for cart in result.json()] == [
        cart_ids[i] for i in expected_indices
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"min_price": -1},
        {"max_price": -1},
        {"min_quantity": -1},
        {"max_quantity": -1},
    ],
)
def test_cart_filter_validation(client, params):
    assert (
        client.get("/cart", params=params).status_code
        == HTTPStatus.UNPROCESSABLE_ENTITY
    )
