import pytest


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/item/999999", None),
    ("PUT", "/item/999999", {"name": "Book", "price": 10}),
    ("PATCH", "/item/999999", {"price": 10}),
    ("DELETE", "/item/999999", None),
    ("GET", "/cart/999999", None),
    ("POST", "/cart/999999/add/999999", None),
])
def test_missing_resource(client, method, path, body):
    assert client.request(method, path, json=body).status_code == 404


@pytest.mark.parametrize("body", [{"name": None}, {"price": None}, {"price": -1}, {"id": 2}])
def test_invalid_patch_preserves_item(client, body):
    item = client.post("/item", json={"name": "Book", "price": 10}).json()
    assert client.patch(f"/item/{item['id']}", json=body).status_code == 422
    assert client.get(f"/item/{item['id']}").json() == item


def test_deleted_item_stays_in_cart_as_unavailable(client):
    item = client.post("/item", json={"name": "Book", "price": 10}).json()
    cart = client.post("/cart").json()
    path = f"/cart/{cart['id']}/add/{item['id']}"
    assert client.post(path).status_code == 200
    assert client.post(path).status_code == 200
    assert client.get(f"/cart/{cart['id']}").json()["price"] == 20
    client.delete(f"/item/{item['id']}")
    result = client.get(f"/cart/{cart['id']}").json()
    assert result["price"] == 0
    assert result["items"] == [{"id": item["id"], "name": "Book", "quantity": 2, "available": False}]
    assert client.post(path).status_code == 404
    assert client.post(f"/cart/{cart['id']}/add/999999").status_code == 404


def test_cart_uses_updated_item_data(client):
    item = client.post("/item", json={"name": "Book", "price": 10}).json()
    cart = client.post("/cart").json()
    client.post(f"/cart/{cart['id']}/add/{item['id']}")
    client.put(f"/item/{item['id']}", json={"name": "New book", "price": 25})
    result = client.get(f"/cart/{cart['id']}").json()
    assert result["price"] == 25
    assert result["items"][0]["name"] == "New book"


def test_item_filters_and_pagination(client):
    items = [client.post("/item", json={"name": str(price), "price": price}).json()
             for price in (0, 10, 20)]
    client.delete(f"/item/{items[1]['id']}")
    assert client.get("/item").json() == [items[0], items[2]]
    deleted = {**items[1], "deleted": True}
    assert client.get("/item", params={"min_price": 10, "max_price": 20, "show_deleted": True}).json() == [deleted, items[2]]
    assert client.get("/item", params={"offset": 1, "limit": 1}).json() == [items[2]]
    assert client.get("/item", params={"offset": 10}).json() == []


@pytest.mark.parametrize("query,indices", [
    ({"min_price": 10, "max_price": 20}, [1, 2]),
    ({"min_quantity": 1, "max_quantity": 1}, [1]),
    ({"min_quantity": 2, "max_quantity": 2}, [2]),
    ({"max_price": 0}, [0]),
    ({"offset": 1, "limit": 1}, [1]),
    ({"min_price": 30}, []),
])
def test_cart_filters(client, query, indices):
    item = client.post("/item", json={"name": "Book", "price": 10}).json()
    carts = [client.post("/cart").json() for _ in range(3)]
    for quantity, cart in enumerate(carts):
        for _ in range(quantity):
            client.post(f"/cart/{cart['id']}/add/{item['id']}")
    result = client.get("/cart", params=query).json()
    assert [cart["id"] for cart in result] == [carts[index]["id"] for index in indices]


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/item", {}),
    ("POST", "/item", {"name": "Book", "price": -1}),
    ("POST", "/item", {"name": "Book", "price": "NaN"}),
    ("GET", "/item/not-a-number", None),
    ("GET", "/cart/not-a-number", None),
    ("GET", "/cart?limit=1.5", None),
    ("GET", "/item?min_price=Infinity", None),
])
def test_invalid_request(client, method, path, body):
    assert client.request(method, path, json=body).status_code == 422


def test_metrics(client):
    client.get("/item")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
