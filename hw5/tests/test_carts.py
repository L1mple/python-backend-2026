from concurrent.futures import ThreadPoolExecutor

import pytest


def ids(resp) -> list[int]:
    return [x["id"] for x in resp.json()]


def add(client, cart_id: int, item_id: int):
    resp = client.post(f"/cart/{cart_id}/add/{item_id}")
    assert resp.status_code == 200
    return resp.json()


def test_create_cart(client):
    resp = client.post("/cart")
    assert resp.status_code == 201
    assert resp.json() == {"id": 1}
    assert resp.headers["Location"] == "/cart/1"


def test_get_empty_cart(client, make_cart):
    cart_id = make_cart()
    resp = client.get(f"/cart/{cart_id}")
    assert resp.status_code == 200
    assert resp.json() == {"id": cart_id, "items": [], "price": 0.0}


def test_get_missing_cart(client):
    assert client.get("/cart/999").status_code == 404


def test_add_item_and_increment_quantity(client, make_item, make_cart):
    item = make_item("milk", 10.0)
    cart_id = make_cart()

    cart = add(client, cart_id, item["id"])
    assert cart["items"] == [
        {"id": item["id"], "name": "milk", "quantity": 1, "available": True}
    ]
    assert cart["price"] == pytest.approx(10.0)

    cart = add(client, cart_id, item["id"])
    assert cart["items"][0]["quantity"] == 2
    assert cart["price"] == pytest.approx(20.0)


def test_add_several_items_keeps_insertion_order(client, make_item, make_cart):
    first = make_item("first", 1.0)
    second = make_item("second", 2.0)
    cart_id = make_cart()

    add(client, cart_id, second["id"])
    cart = add(client, cart_id, first["id"])

    assert [i["name"] for i in cart["items"]] == ["second", "first"]
    assert cart["price"] == pytest.approx(3.0)


def test_add_to_missing_cart(client, make_item):
    item = make_item()
    assert client.post(f"/cart/999/add/{item['id']}").status_code == 404


def test_add_missing_item(client, make_cart):
    cart_id = make_cart()
    assert client.post(f"/cart/{cart_id}/add/999").status_code == 404


def test_cart_reflects_item_price_change(client, make_item, make_cart):
    item = make_item("a", 10.0)
    cart_id = make_cart()
    add(client, cart_id, item["id"])

    client.put(f"/item/{item['id']}", json={"name": "renamed", "price": 50.0})

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["name"] == "renamed"
    assert cart["price"] == pytest.approx(50.0)


def test_deleted_item_is_unavailable_but_still_counted(client, make_item, make_cart):
    item = make_item("a", 10.0)
    cart_id = make_cart()
    add(client, cart_id, item["id"])

    client.delete(f"/item/{item['id']}")

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["available"] is False
    assert cart["price"] == pytest.approx(10.0)


def test_concurrent_adds_do_not_lose_increments(client, make_item, make_cart):
    """Атомарный upsert: 20 параллельных запросов -> ровно quantity == 20."""
    item = make_item("a", 1.0)
    cart_id = make_cart()

    def call(_):
        return client.post(f"/cart/{cart_id}/add/{item['id']}").status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(call, range(20)))

    assert statuses == [200] * 20
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["quantity"] == 20
    assert cart["price"] == pytest.approx(20.0)


@pytest.fixture
def three_carts(client, make_item, make_cart):
    """
    cart 1: пустая                  -> price 0,   qty 0
    cart 2: 2 x A(10)               -> price 20,  qty 2
    cart 3: A(10) + B(100)          -> price 110, qty 2
    """
    a = make_item("A", 10.0)
    b = make_item("B", 100.0)
    c1, c2, c3 = make_cart(), make_cart(), make_cart()
    add(client, c2, a["id"])
    add(client, c2, a["id"])
    add(client, c3, a["id"])
    add(client, c3, b["id"])
    return c1, c2, c3


def test_list_carts_all(client, three_carts):
    assert ids(client.get("/cart")) == [1, 2, 3]


def test_list_carts_price_filters(client, three_carts):
    assert ids(client.get("/cart", params={"min_price": 20})) == [2, 3]
    assert ids(client.get("/cart", params={"max_price": 20})) == [1, 2]
    assert ids(client.get("/cart", params={"min_price": 21, "max_price": 109})) == []


def test_list_carts_quantity_filters(client, three_carts):
    assert ids(client.get("/cart", params={"min_quantity": 1})) == [2, 3]
    assert ids(client.get("/cart", params={"max_quantity": 1})) == [1]
    assert ids(client.get("/cart", params={"min_quantity": 3})) == []


def test_list_carts_pagination(client, three_carts):
    assert ids(client.get("/cart", params={"offset": 1, "limit": 1})) == [2]


def test_list_carts_returns_full_cart_data(client, three_carts):
    carts = client.get("/cart", params={"min_price": 100}).json()
    assert len(carts) == 1
    assert carts[0]["price"] == pytest.approx(110.0)
    assert [i["name"] for i in carts[0]["items"]] == ["A", "B"]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"offset": -1},
        {"min_price": -1},
        {"max_price": -1},
        {"min_quantity": -1},
        {"max_quantity": -1},
    ],
)
def test_list_carts_validation(client, params):
    assert client.get("/cart", params=params).status_code == 422