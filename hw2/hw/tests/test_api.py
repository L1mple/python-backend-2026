import pytest
from sqlalchemy import event
from sqlalchemy.dialects import mssql

from shop_api.database import engine


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/item/999999", None),
        ("put", "/item/999999", {"name": "Missing", "price": 1.0}),
        ("patch", "/item/999999", {"price": 1.0}),
        ("delete", "/item/999999", None),
        ("get", "/cart/999999", None),
        ("post", "/cart/999999/add/999999", None),
    ],
)
def test_missing_resource(client, method, path, body):
    response = client.request(method, path, json=body)

    assert response.status_code == 404


def test_add_missing_or_deleted_item(client, cart, item):
    path = f"/cart/{cart['id']}/add"
    assert client.post(f"{path}/999999").status_code == 404
    assert client.delete(f"/item/{item['id']}").status_code == 200
    assert client.post(f"{path}/{item['id']}").status_code == 404
    assert client.get(f"/item/{item['id']}").status_code == 404
    assert client.get(f"/cart/{cart['id']}").json()["items"] == []


@pytest.mark.parametrize("method", ["post", "put", "patch"])
@pytest.mark.parametrize("price", [-1, "10", True, None])
def test_invalid_price(client, item, method, price):
    path = "/item" if method == "post" else f"/item/{item['id']}"
    response = client.request(method, path, json={"name": "Milk", "price": price})

    assert response.status_code == 422
    assert client.get(f"/item/{item['id']}").json() == item


@pytest.mark.parametrize("method", ["post", "put", "patch"])
@pytest.mark.parametrize("name", ["", None])
def test_invalid_name(client, item, method, name):
    path = "/item" if method == "post" else f"/item/{item['id']}"
    response = client.request(method, path, json={"name": name, "price": 10.0})

    assert response.status_code == 422
    assert client.get(f"/item/{item['id']}").json() == item


@pytest.mark.parametrize("field", ["deleted", "unknown"])
def test_patch_forbids_other_fields(client, item, field):
    response = client.patch(f"/item/{item['id']}", json={field: True})

    assert response.status_code == 422
    assert client.get(f"/item/{item['id']}").json() == item


def test_partial_update_preserves_other_fields(client, item):
    path = f"/item/{item['id']}"
    assert client.patch(path, json={}).json() == item
    response = client.patch(path, json={"name": "New milk"})
    expected = {**item, "name": "New milk"}
    assert response.json() == expected
    assert client.get(path).json() == expected


def test_item_name_preserves_unicode(client):
    data = {"name": "Молоко 牛乳", "price": 10.0}
    response = client.post("/item", json=data)
    assert response.status_code == 201
    item = response.json()

    assert client.get(f"/item/{item['id']}").json() == {
        **data,
        "id": item["id"],
        "deleted": False,
    }


def test_replace_restores_deleted_item(client, item):
    path = f"/item/{item['id']}"
    assert client.delete(path).status_code == 200
    response = client.patch(path, json={"price": 5.0})
    assert response.status_code == 304
    assert response.content == b""
    assert client.delete(path).status_code == 200
    response = client.put(path, json={"name": "Restored", "price": 5.0})
    expected = {"id": item["id"], "name": "Restored", "price": 5.0, "deleted": False}
    assert response.json() == expected
    assert client.get(path).json() == expected


def test_cart_uses_current_item_and_counts_deleted_quantities(client, cart, item):
    cart_path = f"/cart/{cart['id']}"
    item_path = f"/item/{item['id']}"
    for _ in range(2):
        assert client.post(f"{cart_path}/add/{item['id']}").status_code == 200
    assert (
        client.patch(item_path, json={"name": "New milk", "price": 12.5}).status_code
        == 200
    )
    expected = {
        "id": cart["id"],
        "items": [
            {"id": item["id"], "name": "New milk", "quantity": 2, "available": True}
        ],
        "price": 25.0,
    }
    assert client.get(cart_path).json() == expected
    assert client.delete(item_path).status_code == 200
    expected["items"][0]["available"] = False
    expected["price"] = 0.0
    assert client.get(cart_path).json() == expected
    assert client.get(
        "/cart", params={"min_quantity": 2, "max_quantity": 2}
    ).json() == [expected]


@pytest.fixture
def priced_carts(client):
    carts = []
    for quantity in range(3):
        item_id = client.post("/item", json={"name": "Milk", "price": 10.0}).json()[
            "id"
        ]
        cart_id = client.post("/cart").json()["id"]
        for _ in range(quantity):
            assert client.post(f"/cart/{cart_id}/add/{item_id}").status_code == 200
        carts.append(client.get(f"/cart/{cart_id}").json())
    return carts


@pytest.mark.parametrize(
    ("params", "indexes"),
    [
        ({"min_price": 10, "max_price": 10}, [1]),
        ({"min_quantity": 1, "max_quantity": 1}, [1]),
        ({"min_price": 10, "offset": 1, "limit": 1}, [2]),
        ({"min_quantity": 1, "offset": 1, "limit": 1}, [2]),
        ({"max_price": 0, "max_quantity": 0}, [0]),
        ({"offset": 3}, []),
        ({"min_price": 20, "max_price": 10}, []),
        ({"min_quantity": 2, "max_quantity": 1}, []),
    ],
)
def test_cart_filters_before_pagination(client, priced_carts, params, indexes):
    response = client.get("/cart", params=params)

    assert response.status_code == 200
    assert response.json() == [priced_carts[index] for index in indexes]


def test_item_filters_before_pagination(client):
    items = [
        client.post("/item", json={"name": f"Item {price}", "price": price}).json()
        for price in [0.0, 10.0, 20.0, 30.0]
    ]
    assert client.delete(f"/item/{items[1]['id']}").status_code == 200
    items[1]["deleted"] = True
    response = client.get(
        "/item", params={"min_price": 10, "max_price": 30, "offset": 1, "limit": 1}
    )
    assert response.status_code == 200
    assert response.json() == [items[3]]
    response = client.get(
        "/item", params={"min_price": 10, "max_price": 10, "show_deleted": True}
    )
    assert response.json() == [items[1]]
    assert client.get("/item", params={"offset": 100}).json() == []


def test_item_pagination_supports_sql_server(client):
    items = [
        client.post("/item", json={"name": f"Item {i}", "price": float(i)}).json()
        for i in range(3)
    ]

    def compile_for_sql_server(connection, statement, multiparams, params, options):
        statement.compile(dialect=mssql.dialect())

    event.listen(engine, "before_execute", compile_for_sql_server)
    try:
        response = client.get("/item", params={"offset": 1, "limit": 1})
    finally:
        event.remove(engine, "before_execute", compile_for_sql_server)

    assert response.status_code == 200
    assert response.json() == [items[1]]


def test_cart_add_overflow_rolls_back(client, cart):
    item = client.post("/item", json={"name": "Expensive", "price": 1e308}).json()
    cart_path = f"/cart/{cart['id']}"
    first = client.post(f"{cart_path}/add/{item['id']}")
    assert first.status_code == 200
    response = client.post(f"{cart_path}/add/{item['id']}")

    assert response.status_code == 422
    assert client.get(cart_path).json() == first.json()


@pytest.mark.parametrize("method", ["put", "patch"])
def test_item_price_overflow_rolls_back(client, cart, item, method):
    cart_path = f"/cart/{cart['id']}"
    for _ in range(2):
        assert client.post(f"{cart_path}/add/{item['id']}").status_code == 200
    before = client.get(cart_path).json()
    response = client.request(
        method, f"/item/{item['id']}", json={"name": "Huge", "price": 1e308}
    )

    assert response.status_code == 422
    assert client.get(f"/item/{item['id']}").json() == item
    assert client.get(cart_path).json() == before


def test_metrics_available(client):
    assert client.get("/item").status_code == 200
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_request_duration_seconds" in response.text
