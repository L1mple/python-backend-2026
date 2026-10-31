import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from shop_api.database import Item, SessionLocal
from shop_api.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_item(client, name="Milk", price=25.0):
    response = client.post("/item", json={"name": name, "price": price})
    assert response.status_code == 201
    return response.json()


def create_cart(client):
    response = client.post("/cart")
    assert response.status_code == 201
    assert response.headers["location"] == f"/cart/{response.json()['id']}"
    return response.json()["id"]


def test_item_lifecycle(client):
    item = create_item(client)
    item_id = item["id"]
    assert item["deleted"] is False
    assert client.get(f"/item/{item_id}").json() == item

    replaced = client.put(f"/item/{item_id}", json={"name": "Bread", "price": 40})
    assert replaced.status_code == 200
    assert replaced.json() == {"id": item_id, "name": "Bread", "price": 40, "deleted": False}

    patched = client.patch(f"/item/{item_id}", json={"price": 35})
    assert patched.json()["name"] == "Bread"
    assert patched.json()["price"] == 35
    assert client.patch(f"/item/{item_id}", json={}).json() == patched.json()

    with SessionLocal() as db:
        assert db.get(Item, item_id).price == 35

    assert client.delete(f"/item/{item_id}").status_code == 200
    assert client.delete(f"/item/{item_id}").status_code == 200
    assert client.get(f"/item/{item_id}").status_code == 404
    assert client.put(f"/item/{item_id}", json={"name": "New", "price": 5}).status_code == 304
    assert client.patch(f"/item/{item_id}", json={"name": "New"}).status_code == 304


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_missing_item(client, method):
    if method == "get":
        response = client.get("/item/999999999")
    elif method == "put":
        response = client.put("/item/999999999", json={"name": "Missing", "price": 1})
    elif method == "patch":
        response = client.patch("/item/999999999", json={"price": 1})
    else:
        response = client.delete("/item/999999999")
    assert response.status_code == 404


@pytest.mark.parametrize("body", [
    {}, {"name": "Milk"}, {"name": "", "price": 1},
    {"name": "Milk", "price": -1}, {"name": "Milk", "price": "abc"},
    {"name": "Milk", "price": None}, {"name": "Milk", "price": "NaN"},
    {"name": "Milk", "price": "Infinity"},
    {"name": "Milk", "price": 1, "deleted": True},
])
def test_invalid_item(client, body):
    assert client.post("/item", json=body).status_code == 422


@pytest.mark.parametrize("body", [
    {"price": None}, {"name": None}, {"name": ""}, {"price": -1},
    {"price": "NaN"}, {"deleted": True}, {"id": 100}, {"odd": 1},
])
def test_invalid_patch(client, body):
    item = create_item(client)
    assert client.patch(f"/item/{item['id']}", json=body).status_code == 422
    assert client.get(f"/item/{item['id']}").json() == item


def test_item_filters_and_pagination(client):
    first = create_item(client, "Filter first", 101.25)
    second = create_item(client, "Filter second", 102.25)
    third = create_item(client, "Filter third", 103.25)
    params = {"min_price": 101.25, "max_price": 103.25, "limit": 10000}
    items = client.get("/item", params=params).json()
    ids = []
    for item in items:
        ids.append(item["id"])
        assert item["price"] >= 101.25
        assert item["price"] <= 103.25
    assert first["id"] in ids
    assert second["id"] in ids
    assert third["id"] in ids
    params["offset"] = 1
    params["limit"] = 1
    assert client.get("/item", params=params).json() == items[1:2]

    client.delete(f"/item/{second['id']}")
    response = client.get("/item", params={"limit": 10000})
    for item in response.json():
        assert item["id"] != second["id"]
    deleted = client.get("/item", params={"show_deleted": True, "limit": 10000}).json()
    found_deleted_item = False
    for item in deleted:
        if item["id"] == second["id"]:
            assert item["deleted"] is True
            found_deleted_item = True
    assert found_deleted_item
    assert client.get("/item", params={"min_price": 100, "max_price": 1}).json() == []


def test_cart_lifecycle(client):
    cart_id = create_cart(client)
    assert client.get(f"/cart/{cart_id}").json() == {"id": cart_id, "items": [], "price": 0}
    milk = create_item(client, "Milk for cart", 25.5)
    bread = create_item(client, "Bread for cart", 10)
    for item in (milk, milk, bread):
        assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 200
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["price"] == pytest.approx(61)
    assert cart["items"] == [
        {"id": milk["id"], "name": milk["name"], "quantity": 2, "available": True},
        {"id": bread["id"], "name": bread["name"], "quantity": 1, "available": True},
    ]

    client.patch(f"/item/{milk['id']}", json={"name": "Changed milk", "price": 30})
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["price"] == 70
    assert cart["items"][0]["name"] == "Changed milk"

    client.delete(f"/item/{milk['id']}")
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["available"] is False
    assert cart["price"] == 10
    assert client.post(f"/cart/{cart_id}/add/{milk['id']}").status_code == 404


def test_missing_cart_or_item(client):
    item = create_item(client)
    cart_id = create_cart(client)
    assert client.get("/cart/999999999").status_code == 404
    assert client.post(f"/cart/999999999/add/{item['id']}").status_code == 404
    assert client.post(f"/cart/{cart_id}/add/999999999").status_code == 404


@pytest.mark.parametrize("params", [
    {"min_price": 0}, {"max_price": 1}, {"min_quantity": 2},
    {"max_quantity": 0}, {"min_price": 0, "max_price": 9999999, "min_quantity": 0, "max_quantity": 100},
])
def test_cart_filters(client, params):
    empty = create_cart(client)
    filled = create_cart(client)
    item = create_item(client, "Cart filter", 155)
    client.post(f"/cart/{filled}/add/{item['id']}")
    client.post(f"/cart/{filled}/add/{item['id']}")
    query = params.copy()
    query["limit"] = 10000
    carts = client.get("/cart", params=query).json()
    cart_ids = []
    for cart in carts:
        cart_ids.append(cart["id"])
        quantity = 0
        for item in cart["items"]:
            quantity += item["quantity"]
        if "min_price" in params:
            assert cart["price"] >= params["min_price"]
        if "max_price" in params:
            assert cart["price"] <= params["max_price"]
        if "min_quantity" in params:
            assert quantity >= params["min_quantity"]
        if "max_quantity" in params:
            assert quantity <= params["max_quantity"]
    if params.get("max_quantity") == 0 or params.get("max_price") == 1:
        assert empty in cart_ids
        assert filled not in cart_ids
    if params.get("min_quantity") == 2:
        assert filled in cart_ids
        assert empty not in cart_ids


def test_cart_pagination(client):
    all_carts = client.get("/cart", params={"limit": 10000}).json()
    page = client.get("/cart", params={"offset": 1, "limit": 2}).json()
    assert page == all_carts[1:3]
    assert client.get("/cart", params={"min_price": 100, "max_price": 1}).json() == []


@pytest.mark.parametrize("path", ["/cart", "/item"])
@pytest.mark.parametrize("query", [
    {"offset": -1}, {"offset": "abc"}, {"limit": 0}, {"limit": -1},
    {"min_price": -1}, {"max_price": -1}, {"min_price": "NaN"},
    {"max_price": "Infinity"},
])
def test_invalid_filters(client, path, query):
    assert client.get(path, params=query).status_code == 422


@pytest.mark.parametrize("query", [{"min_quantity": -1}, {"max_quantity": -1}, {"max_quantity": "abc"}])
def test_invalid_quantity(client, query):
    assert client.get("/cart", params=query).status_code == 422


@pytest.mark.parametrize("path", ["/item/abc", "/cart/abc", "/cart/abc/add/1", "/cart/1/add/abc"])
def test_invalid_path(client, path):
    if "add" in path:
        response = client.post(path)
    else:
        response = client.get(path)
    assert response.status_code == 422


def test_metrics_and_docs(client):
    assert client.get("/docs").status_code == 200
    assert "/item" in client.get("/openapi.json").json()["paths"]
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text
    assert "http_request_duration_seconds" in metrics.text


def test_uncommitted_data_is_rolled_back(client):
    # Исключение закрывает сессию без commit, товар не должен сохраниться.
    with pytest.raises(RuntimeError):
        with SessionLocal() as db:
            db.add(Item(name="Rollback test", price=1))
            db.flush()
            raise RuntimeError("Cancel transaction")
    with SessionLocal() as db:
        assert db.scalar(select(Item).where(Item.name == "Rollback test")) is None
