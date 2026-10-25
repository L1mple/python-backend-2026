import pytest


@pytest.fixture()
def item(isolated_api):
    response = isolated_api.post("/item", json={"name": "Milk", "price": 7.5})
    assert response.status_code == 201
    return response.json()


def test_item_lifecycle(isolated_api, item):
    path = f"/item/{item['id']}"
    assert isolated_api.get(path).json() == item
    response = isolated_api.put(path, json={"name": "Bread", "price": 0})
    assert response.status_code == 200
    assert response.json() == {**item, "name": "Bread", "price": 0}

    response = isolated_api.patch(path, json={"name": "Water", "price": 2.5})
    assert response.status_code == 200
    expected = {**item, "name": "Water", "price": 2.5}
    assert response.json() == expected
    assert isolated_api.patch(path, json={}).json() == expected
    assert isolated_api.get(path).json() == expected

    for _ in range(2):
        assert isolated_api.delete(path).status_code == 200
    assert isolated_api.get(path).status_code == 404
    assert isolated_api.get("/item").json() == []
    assert isolated_api.get("/item", params={"show_deleted": True}).json() == [
        {**expected, "deleted": True}
    ]
    response = isolated_api.patch(path, json={"name": "ignored"})
    assert response.status_code == 304
    assert response.content == b""
    response = isolated_api.put(path, json={"name": "Restored", "price": 4})
    assert response.status_code == 200
    assert isolated_api.get(path).json() == {**item, "name": "Restored", "price": 4}


def test_created_resources_have_working_locations(isolated_api):
    for path, body in [("/item", {"name": "Free", "price": 0}), ("/cart", None)]:
        response = isolated_api.post(path, json=body)
        assert response.status_code == 201
        location = response.headers["location"]
        assert location == f"{path}/{response.json()['id']}"
        assert isolated_api.get(location).status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch"])
@pytest.mark.parametrize(
    "invalid",
    [
        {"name": None},
        {"price": None},
        {"price": -0.01},
        {"price": "NaN"},
        {"price": "Infinity"},
        {"extra": "forbidden"},
    ],
)
def test_invalid_item_data_does_not_change_state(isolated_api, item, method, invalid):
    path = "/item" if method == "post" else f"/item/{item['id']}"
    response = isolated_api.request(
        method, path, json={"name": "New", "price": 2, **invalid}
    )
    assert response.status_code == 422
    assert isolated_api.get(f"/item/{item['id']}").json() == item
    assert isolated_api.get("/item").json() == [item]


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize("body", [{}, {"name": "Missing price"}, {"price": 1}])
def test_required_item_fields(isolated_api, item, method, body):
    path = "/item" if method == "post" else f"/item/{item['id']}"
    assert isolated_api.request(method, path, json=body).status_code == 422
    assert isolated_api.get("/item").json() == [item]


def test_patch_cannot_change_deleted_flag(isolated_api, item):
    response = isolated_api.patch(f"/item/{item['id']}", json={"deleted": True})
    assert response.status_code == 422
    assert isolated_api.get(f"/item/{item['id']}").json() == item


@pytest.mark.parametrize(
    "query,indices",
    [
        ({"min_price": 10, "max_price": 20}, [1, 2]),
        ({"min_price": 10, "max_price": 10}, [1]),
        ({"min_price": 20, "max_price": 10}, []),
        ({"offset": 1, "limit": 1}, [1]),
        ({"offset": 50}, []),
        ({"show_deleted": True, "offset": 2, "limit": 1}, [2]),
    ],
)
def test_item_filters_and_pagination(isolated_api, query, indices):
    items = [
        isolated_api.post("/item", json={"name": f"Item {i}", "price": price}).json()
        for i, price in enumerate([0, 10, 20, 30])
    ]
    isolated_api.delete(f"/item/{items[3]['id']}")
    response = isolated_api.get("/item", params=query)
    assert response.status_code == 200
    assert response.json() == [items[i] for i in indices]


def test_cart_price_quantity_and_deleted_items(isolated_api, item):
    cart_id = isolated_api.post("/cart").json()["id"]
    path = f"/cart/{cart_id}"
    assert isolated_api.get(path).json() == {"id": cart_id, "items": [], "price": 0}
    for quantity in [1, 2]:
        response = isolated_api.post(f"{path}/add/{item['id']}")
        assert response.status_code == 200
        assert response.json() == {
            "id": cart_id,
            "items": [
                {
                    "id": item["id"],
                    "name": "Milk",
                    "quantity": quantity,
                    "available": True,
                }
            ],
            "price": 7.5 * quantity,
        }

    isolated_api.patch(f"/item/{item['id']}", json={"name": "Changed", "price": 3})
    cart = isolated_api.get(path).json()
    assert cart["items"][0]["name"] == "Changed"
    assert cart["price"] == 6
    isolated_api.delete(f"/item/{item['id']}")
    deleted_cart = {
        **cart,
        "price": 0,
        "items": [{**cart["items"][0], "available": False}],
    }
    assert isolated_api.get(path).json() == deleted_cart
    assert isolated_api.post(f"{path}/add/{item['id']}").status_code == 404
    assert isolated_api.get(path).json() == deleted_cart
    assert isolated_api.get(
        "/cart", params={"min_quantity": 2, "max_quantity": 2, "max_price": 0}
    ).json() == [deleted_cart]


@pytest.mark.parametrize(
    "query,indices",
    [
        ({"min_price": 15, "max_price": 15}, [2]),
        ({"min_quantity": 1, "max_quantity": 1}, [1]),
        ({"min_price": 7.5, "offset": 1, "limit": 1}, [2]),
        ({"min_quantity": 1, "offset": 1, "limit": 1}, [2]),
        ({"max_price": 0, "max_quantity": 0}, [0]),
        ({"offset": 50}, []),
        ({"min_price": 20, "max_price": 10}, []),
        ({"min_quantity": 3, "max_quantity": 1}, []),
    ],
)
def test_cart_filters_apply_before_pagination(isolated_api, item, query, indices):
    carts = []
    for quantity in range(3):
        cart_id = isolated_api.post("/cart").json()["id"]
        for _ in range(quantity):
            isolated_api.post(f"/cart/{cart_id}/add/{item['id']}")
        carts.append(isolated_api.get(f"/cart/{cart_id}").json())
    response = isolated_api.get("/cart", params=query)
    assert response.status_code == 200
    assert response.json() == [carts[i] for i in indices]


@pytest.mark.parametrize("path", ["/item", "/cart"])
@pytest.mark.parametrize(
    "query",
    [
        {"offset": -1},
        {"limit": 0},
        {"offset": "bad"},
        {"min_price": "NaN"},
        {"max_price": "Infinity"},
    ],
)
def test_invalid_filters(isolated_api, path, query):
    assert isolated_api.get(path, params=query).status_code == 422


def test_failed_additions_leave_cart_unchanged(isolated_api, item):
    cart_id = isolated_api.post("/cart").json()["id"]
    assert isolated_api.post(f"/cart/{cart_id}/add/-1").status_code == 404
    assert isolated_api.post(f"/cart/-1/add/{item['id']}").status_code == 404
    assert isolated_api.get(f"/cart/{cart_id}").json() == {
        "id": cart_id,
        "items": [],
        "price": 0,
    }
