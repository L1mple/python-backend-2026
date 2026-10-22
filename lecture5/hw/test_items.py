from http import HTTPStatus
import pytest


def test_create_item(client):
    response = client.post("/item", json={"name": "Кофе", "price": 300.5})

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["name"] == "Кофе"
    assert data["price"] == 300.5
    assert data["deleted"] is False
    assert response.headers["location"] == f"/item/{data['id']}"


@pytest.mark.parametrize(
    "body",
    [
        {"name": "Кофе"},
        {"price": 100},
        {"name": "", "price": 100},
        {"name": "Кофе", "price": -1},
        {"name": "Кофе", "price": 100, "extra": 1},
    ],
)
def test_create_item_invalid(client, body):
    response = client.post("/item", json=body)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_get_item(client, item):
    response = client.get(f"/item/{item['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == item


def test_get_item_not_found(client):
    assert client.get("/item/999").status_code == HTTPStatus.NOT_FOUND


def test_get_deleted_item(client, deleted_item):
    response = client.get(f"/item/{deleted_item['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("params", "expected_prices"),
    [
        ({}, [50.0, 100.0, 150.0, 200.0, 250.0]),
        ({"min_price": 150}, [150.0, 200.0, 250.0]),
        ({"max_price": 100}, [50.0, 100.0]),
        ({"offset": 1, "limit": 2}, [100.0, 150.0]),
    ],
)
def test_get_items_with_filters(client, items, params, expected_prices):
    response = client.get("/item", params=params)

    assert response.status_code == HTTPStatus.OK
    assert [i["price"] for i in response.json()] == expected_prices


def test_get_items_show_deleted(client, items):
    client.delete(f"/item/{items[0]['id']}")

    assert len(client.get("/item").json()) == 4
    assert len(client.get("/item", params={"show_deleted": True}).json()) == 5


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"min_price": -1}])
def test_get_items_bad_params(client, params):
    response = client.get("/item", params=params)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_put_item(client, item):
    response = client.put(f"/item/{item['id']}", json={"name": "Зеленый чай", "price": 180.0})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "Зеленый чай"
    assert response.json()["price"] == 180.0


def test_put_deleted_item(client, deleted_item):
    response = client.put(f"/item/{deleted_item['id']}", json={"name": "Кофе", "price": 300.0})
    assert response.status_code == HTTPStatus.NOT_MODIFIED


def test_put_item_not_found(client):
    response = client.put("/item/999", json={"name": "Кофе", "price": 300.0})
    assert response.status_code == HTTPStatus.NOT_MODIFIED


@pytest.mark.parametrize(
    ("body", "expected_name", "expected_price"),
    [
        ({"name": "Пуэр"}, "Пуэр", 150.0),
        ({"price": 200.0}, "Чай", 200.0),
    ],
)
def test_patch_item(client, item, body, expected_name, expected_price):
    response = client.patch(f"/item/{item['id']}", json=body)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == expected_name
    assert response.json()["price"] == expected_price


def test_patch_deleted_item(client, deleted_item):
    response = client.patch(f"/item/{deleted_item['id']}", json={"price": 1.0})
    assert response.status_code == HTTPStatus.NOT_MODIFIED


def test_patch_item_not_found(client):
    response = client.patch("/item/999", json={"price": 1.0})
    assert response.status_code == HTTPStatus.NOT_MODIFIED


@pytest.mark.parametrize("body", [{"deleted": True}, {"price": 0}])
def test_patch_item_invalid(client, item, body):
    response = client.patch(f"/item/{item['id']}", json=body)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_delete_item(client, item):
    response = client.delete(f"/item/{item['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["deleted"] is True
    assert client.delete(f"/item/{item['id']}").status_code == HTTPStatus.OK


def test_delete_item_not_found(client):
    assert client.delete("/item/999").status_code == HTTPStatus.NOT_FOUND
