from http import HTTPStatus

import pytest


def test_create_item(client, item_data):
    response = client.post("/item", json=item_data)

    assert response.status_code == HTTPStatus.CREATED
    result = response.json()
    assert isinstance(result["id"], int)
    assert result["id"] > 0
    assert result == {"id": result["id"], **item_data, "deleted": False}
    assert response.headers["Location"] == f"/item/{result['id']}"


def test_get_item(client, item):
    response = client.get(f"/item/{item['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == item


def test_get_items_empty(client):
    response = client.get("/item")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


@pytest.mark.parametrize(
    ("query", "indices"),
    [
        ({}, [0, 1, 2]),
        ({"min_price": 20}, [1, 2]),
        ({"max_price": 20}, [0, 1]),
        ({"min_price": 20, "max_price": 20}, [1]),
        ({"min_price": 30, "max_price": 10}, []),
        ({"offset": 1, "limit": 1}, [1]),
        ({"min_price": 20, "offset": 1, "limit": 1}, [2]),
    ],
)
def test_get_items_filters_and_pagination(client, create_item, query, indices):
    items = [create_item(name=f"Item {price}", price=price) for price in (10, 20, 30)]

    response = client.get("/item", params=query)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == [items[index] for index in indices]


def test_deleted_item_is_hidden_until_requested(client, item):
    response = client.delete(f"/item/{item['id']}")

    assert response.status_code == HTTPStatus.OK
    assert client.get(f"/item/{item['id']}").status_code == HTTPStatus.NOT_FOUND
    assert client.get("/item").json() == []
    assert client.get("/item", params={"show_deleted": True}).json() == [
        {**item, "deleted": True}
    ]
    assert client.delete(f"/item/{item['id']}").status_code == HTTPStatus.OK


def test_replace_item(client, item):
    body = {"name": "Replacement", "price": 27.5}

    response = client.put(f"/item/{item['id']}", json=body)

    assert response.status_code == HTTPStatus.OK
    expected = {"id": item["id"], **body, "deleted": False}
    assert response.json() == expected
    assert client.get(f"/item/{item['id']}").json() == expected


def test_replace_can_restore_deleted_item(client, item):
    client.delete(f"/item/{item['id']}")
    body = {"name": "Restored", "price": 5}

    response = client.put(f"/item/{item['id']}", json=body)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["deleted"] is False
    assert client.get(f"/item/{item['id']}").status_code == HTTPStatus.OK


def test_replace_can_mark_item_deleted(client, item):
    body = {"name": "Unavailable", "price": 5, "deleted": True}

    response = client.put(f"/item/{item['id']}", json=body)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"id": item["id"], **body}
    assert client.get(f"/item/{item['id']}").status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("changes", [{}, {"name": "New name"}, {"price": 0}])
def test_patch_changes_only_provided_fields(client, item, changes):
    response = client.patch(f"/item/{item['id']}", json=changes)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {**item, **changes}
    assert client.get(f"/item/{item['id']}").json() == response.json()


def test_patch_deleted_item_does_not_change_it(client, item):
    client.delete(f"/item/{item['id']}")

    response = client.patch(f"/item/{item['id']}", json={"name": "Changed"})

    assert response.status_code == HTTPStatus.NOT_MODIFIED
    assert response.content == b""
    assert client.get("/item", params={"show_deleted": True}).json() == [
        {**item, "deleted": True}
    ]


@pytest.mark.parametrize(
    ("method", "body"),
    [("GET", None), ("PUT", {"name": "Missing", "price": 10}), ("PATCH", {}), ("DELETE", None)],
)
def test_missing_item(client, method, body):
    response = client.request(method, "/item/-1", json=body)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Item not found"}


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("POST", {}),
        ("POST", {"price": 10}),
        ("POST", {"name": "Missing price"}),
        ("POST", {"name": "Negative", "price": -1}),
        ("POST", {"name": "Extra", "price": 10, "extra": True}),
        ("PUT", {"name": "Invalid price", "price": "abc"}),
        ("PATCH", {"price": -1}),
        ("PATCH", {"deleted": True}),
        ("PATCH", {"extra": True}),
    ],
)
def test_invalid_item_body(client, item, method, body):
    path = "/item" if method == "POST" else f"/item/{item['id']}"

    response = client.request(method, path, json=body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.get(f"/item/{item['id']}").json() == item


@pytest.mark.parametrize("field", ["name", "price"])
def test_patch_rejects_explicit_null(client, item, field):
    response = client.patch(f"/item/{item['id']}", json={field: None})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {"detail": f"{field.capitalize()} cannot be null"}
    assert client.get(f"/item/{item['id']}").json() == item


@pytest.mark.parametrize(
    "query",
    [{"offset": -1}, {"limit": 0}, {"min_price": -1}, {"max_price": -1}],
)
def test_invalid_item_query(client, query):
    response = client.get("/item", params=query)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY