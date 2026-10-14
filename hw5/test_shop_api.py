import os
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


# Fail before importing the application: tests must never use its default DB.
test_database_url = os.environ.get("TEST_DATABASE_URL")
if not test_database_url:
    raise pytest.UsageError("Set TEST_DATABASE_URL to a dedicated PostgreSQL database named shop_test")
url = make_url(test_database_url)
if url.get_backend_name() != "postgresql" or url.database != "shop_test":
    raise pytest.UsageError("TEST_DATABASE_URL must point to a PostgreSQL database named shop_test")
os.environ["DATABASE_URL"] = test_database_url

from shop_api.database import engine, get_session  # noqa: E402
from shop_api.main import app  # noqa: E402
from shop_api.models import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(database):
    def clear():
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE cart_items, carts, items RESTART IDENTITY"))

    clear()
    yield
    clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_item(client, name="Milk", price=10):
    response = client.post("/item", json={"name": name, "price": price})
    assert response.status_code == 201
    return response.json()


def create_cart(client):
    response = client.post("/cart")
    assert response.status_code == 201
    cart_id = response.json()["id"]
    assert response.headers["Location"] == f"/cart/{cart_id}"
    return cart_id


def test_item_lifecycle(client):
    item = create_item(client)
    item_url = f"/item/{item['id']}"
    assert item == {"id": item["id"], "name": "Milk", "price": 10, "deleted": False}
    assert client.get(item_url).json() == item

    response = client.put(item_url, json={"name": "Bread", "price": 20})
    assert response.status_code == 200
    assert response.json() == {**item, "name": "Bread", "price": 20}
    assert client.get(item_url).json() == response.json()

    for changes in ({"name": "Water"}, {"price": 0}, {"name": "Tea", "price": 0.1}, {}):
        before = client.get(item_url).json()
        response = client.patch(item_url, json=changes)
        assert response.status_code == 200
        assert response.json() == {**before, **changes}
        assert client.get(item_url).json() == response.json()

    for _ in range(2):
        response = client.delete(item_url)
        assert response.status_code == 200
        assert response.json() == {"detail": "Item deleted"}
    assert client.get(item_url).status_code == 404
    assert client.get("/item").json() == []
    deleted = client.get("/item", params={"show_deleted": True}).json()
    assert deleted == [{**item, "name": "Tea", "price": 0.1, "deleted": True}]
    assert client.put(item_url, json={"name": "Back", "price": 5}).status_code == 404
    response = client.patch(item_url, json={"name": "Back"})
    assert response.status_code == 304
    assert response.content == b""
    assert client.get("/item", params={"show_deleted": True}).json() == deleted


@pytest.mark.parametrize("method,body", [
    ("get", None), ("delete", None),
    ("put", {"name": "Missing", "price": 1}), ("patch", {"price": 1}),
])
def test_missing_item(client, method, body):
    response = client.request(method, "/item/999", json=body)
    assert response.status_code == 404
    assert response.json() == {"detail": "Item 999 not found"}


@pytest.mark.parametrize("method,body", [
    ("post", {}), ("post", {"name": "Milk"}), ("post", {"price": 10}),
    ("post", {"name": "Milk", "price": -1}),
    ("post", {"name": "Milk", "price": "NaN"}),
    ("post", {"name": "Milk", "price": "Infinity"}),
    ("post", {"name": None, "price": 1}),
    ("put", {"name": "Milk"}), ("put", {"price": 1}),
    ("put", {"name": "Milk", "price": -1}),
    ("put", {"name": "Milk", "price": None}),
    ("patch", {"name": None}), ("patch", {"price": None}),
    ("patch", {"price": -1}), ("patch", {"price": "Infinity"}),
    ("patch", {"deleted": True}), ("patch", {"id": 999}),
])
def test_invalid_item_body(client, method, body):
    item = create_item(client)
    path = "/item" if method == "post" else f"/item/{item['id']}"
    assert client.request(method, path, json=body).status_code == 422
    assert client.get("/item").json() == [item]


@pytest.mark.parametrize("params,indices", [
    ({}, [0, 1, 2]),
    ({"min_price": 10}, [1, 2]),
    ({"max_price": 10}, [0, 1]),
    ({"min_price": 10, "max_price": 10}, [1]),
    ({"min_price": 20, "max_price": 10}, []),
    ({"show_deleted": True}, [0, 1, 2, 3]),
    ({"offset": 1, "limit": 1}, [1]),
    ({"min_price": 10, "offset": 1, "limit": 1}, [2]),
    ({"offset": 99}, []),
])
def test_item_filters(client, params, indices):
    items = [create_item(client, f"Item {i}", price) for i, price in enumerate([0, 10, 20, 30])]
    assert client.delete(f"/item/{items[3]['id']}").status_code == 200
    items[3]["deleted"] = True
    response = client.get("/item", params=params)
    assert response.status_code == 200
    assert response.json() == [items[i] for i in indices]


@pytest.mark.parametrize("path,params", [
    ("/item", {"offset": -1}), ("/item", {"limit": 0}),
    ("/item", {"min_price": -1}), ("/item", {"max_price": -1}),
    ("/item", {"show_deleted": "wrong"}), ("/item", {"limit": "wrong"}),
    ("/cart", {"offset": -1}), ("/cart", {"limit": 0}),
    ("/cart", {"min_price": -1}), ("/cart", {"max_price": -1}),
    ("/cart", {"min_quantity": -1}), ("/cart", {"max_quantity": -1}),
    ("/cart", {"min_quantity": 1.5}),
    ("/item/wrong", {}), ("/cart/wrong", {}),
])
def test_invalid_query_or_id(client, path, params):
    assert client.get(path, params=params).status_code == 422


def test_empty_lists(client):
    assert client.get("/item").json() == []
    assert client.get("/cart").json() == []


def test_cart_lifecycle(client):
    cart_id = create_cart(client)
    path = f"/cart/{cart_id}"
    assert client.get(path).json() == {"id": cart_id, "items": [], "price": 0}
    first = create_item(client, "First", 0.1)
    second = create_item(client, "Second", 0.2)
    for item in (first, first, second):
        response = client.post(f"{path}/add/{item['id']}")
        assert response.status_code == 200
        assert response.json() == {"detail": "Item added"}
    expected = {
        "id": cart_id,
        "items": [
            {"id": first["id"], "name": "First", "quantity": 2, "available": True},
            {"id": second["id"], "name": "Second", "quantity": 1, "available": True},
        ],
        "price": 0.4,
    }
    assert client.get(path).json() == expected

    assert client.patch(f"/item/{first['id']}", json={"name": "Updated", "price": 0.3}).status_code == 200
    expected["items"][0]["name"] = "Updated"
    expected["price"] = 0.8
    assert client.get(path).json() == expected

    assert client.delete(f"/item/{first['id']}").status_code == 200
    expected["items"][0]["available"] = False
    expected["price"] = 0.2
    assert client.get(path).json() == expected
    assert client.get("/cart").json() == [expected]
    assert client.post(f"{path}/add/{first['id']}").status_code == 404
    assert client.get(path).json() == expected


def test_missing_cart_or_item(client):
    item = create_item(client)
    cart_id = create_cart(client)
    response = client.get("/cart/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Cart 999 not found"}
    response = client.post(f"/cart/999/add/{item['id']}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Cart 999 not found"}
    response = client.post(f"/cart/{cart_id}/add/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Item 999 not found"}
    assert client.get(f"/cart/{cart_id}").json()["items"] == []
    # A failed operation must not prevent the next transaction from committing.
    assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 200
    assert client.get(f"/cart/{cart_id}").json()["price"] == 10


@pytest.mark.parametrize("params,indices", [
    ({}, [0, 1, 2, 3]),
    ({"min_price": 20}, [2]),
    ({"max_price": 10}, [0, 1, 3]),
    ({"min_price": 10, "max_price": 10}, [1]),
    ({"min_quantity": 2}, [2]),
    ({"max_quantity": 1}, [0, 1, 3]),
    ({"min_quantity": 1, "max_quantity": 1}, [1, 3]),
    ({"min_price": 0, "max_price": 0, "min_quantity": 1, "max_quantity": 1}, [3]),
    ({"offset": 1, "limit": 2}, [1, 2]),
    ({"min_quantity": 1, "offset": 1, "limit": 1}, [2]),
    ({"offset": 99}, []),
    ({"min_price": 20, "max_price": 10}, []),
])
def test_cart_filters(client, params, indices):
    item = create_item(client, price=10)
    deleted = create_item(client, "Deleted", 100)
    ids = [create_cart(client) for _ in range(4)]
    for cart_id, item_id in [(ids[1], item["id"]), (ids[2], item["id"]),
                             (ids[2], item["id"]), (ids[3], deleted["id"])]:
        assert client.post(f"/cart/{cart_id}/add/{item_id}").status_code == 200
    assert client.delete(f"/item/{deleted['id']}").status_code == 200
    expected = [client.get(f"/cart/{cart_id}").json() for cart_id in ids]
    response = client.get("/cart", params=params)
    assert response.status_code == 200
    assert response.json() == [expected[i] for i in indices]


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_database_failure(client):
    session = Mock(spec=Session)
    session.execute.side_effect = SQLAlchemyError("Database unavailable")
    app.dependency_overrides[get_session] = lambda: session
    try:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "database unavailable"}
        session.execute.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_session)


def test_metrics(client):
    def samples():
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        return [sample for family in text_string_to_metric_families(response.text)
                for sample in family.samples]

    def shop_values():
        return {sample.name: sample.value for sample in samples() if not sample.labels}

    before = shop_values()
    first = create_item(client)
    second = create_item(client)
    cart_id = create_cart(client)
    for _ in range(2):
        assert client.post(f"/cart/{cart_id}/add/{first['id']}").status_code == 200
    assert client.delete(f"/item/{second['id']}").status_code == 200
    assert client.post(f"/cart/{cart_id}/add/{second['id']}").status_code == 404
    assert client.post("/item", json={"name": "Invalid", "price": -1}).status_code == 422
    after = shop_values()
    assert after["shop_items_created_total"] - before["shop_items_created_total"] == 2
    assert after["shop_carts_created_total"] - before["shop_carts_created_total"] == 1
    assert after["shop_cart_additions_total"] - before["shop_cart_additions_total"] == 2
    assert after["shop_available_items"] == 1
    assert after["shop_carts"] == 1
    assert any(sample.name == "http_requests_total"
               and sample.labels.get("handler") == "/item"
               and sample.labels.get("method") == "POST"
               and sample.labels.get("status") == "201"
               and sample.value >= 2 for sample in samples())
