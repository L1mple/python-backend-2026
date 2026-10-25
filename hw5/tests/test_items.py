import pytest


def ids(resp) -> list[int]:
    return [x["id"] for x in resp.json()]


def test_create_item(client):
    resp = client.post("/item", json={"name": "milk", "price": 79.5})
    assert resp.status_code == 201
    assert resp.json() == {"id": 1, "name": "milk", "price": 79.5, "deleted": False}


def test_create_item_validation_error(client):
    resp = client.post("/item", json={"name": "milk"})
    assert resp.status_code == 422


def test_get_item(client, make_item):
    item = make_item("bread", 40.0)
    resp = client.get(f"/item/{item['id']}")
    assert resp.status_code == 200
    assert resp.json() == item


def test_get_missing_item(client):
    assert client.get("/item/999").status_code == 404


def test_get_deleted_item_is_404(client, make_item):
    item = make_item()
    client.delete(f"/item/{item['id']}")
    assert client.get(f"/item/{item['id']}").status_code == 404


def test_list_items_filters_and_pagination(client, make_item):
    for name, price in [("a", 5), ("b", 10), ("c", 20), ("d", 40)]:
        make_item(name, price)

    assert ids(client.get("/item")) == [1, 2, 3, 4]
    assert ids(client.get("/item", params={"min_price": 10})) == [2, 3, 4]
    assert ids(client.get("/item", params={"max_price": 10})) == [1, 2]
    assert ids(client.get("/item", params={"min_price": 10, "max_price": 20})) == [2, 3]
    assert ids(client.get("/item", params={"offset": 1, "limit": 2})) == [2, 3]
    assert ids(client.get("/item", params={"offset": 10})) == []


def test_list_items_show_deleted(client, make_item):
    make_item("a")
    make_item("b")
    client.delete("/item/1")

    assert ids(client.get("/item")) == [2]
    assert ids(client.get("/item", params={"show_deleted": True})) == [1, 2]


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"offset": -1}, {"min_price": -1}, {"max_price": -5}],
)
def test_list_items_validation(client, params):
    assert client.get("/item", params=params).status_code == 422


def test_put_item_replaces_fields_and_restores_deleted(client, make_item):
    item = make_item("old", 1.0)
    client.delete(f"/item/{item['id']}")

    resp = client.put(f"/item/{item['id']}", json={"name": "new", "price": 2.5})
    assert resp.status_code == 200
    assert resp.json() == {"id": item["id"], "name": "new", "price": 2.5, "deleted": False}
    assert client.get(f"/item/{item['id']}").status_code == 200


def test_put_missing_item(client):
    resp = client.put("/item/999", json={"name": "x", "price": 1})
    assert resp.status_code == 404


def test_patch_name_only(client, make_item):
    item = make_item("old", 10.0)
    resp = client.patch(f"/item/{item['id']}", json={"name": "new"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "new"
    assert resp.json()["price"] == 10.0


def test_patch_price_only(client, make_item):
    item = make_item("old", 10.0)
    resp = client.patch(f"/item/{item['id']}", json={"price": 99.0})
    assert resp.status_code == 200
    assert resp.json()["name"] == "old"
    assert resp.json()["price"] == 99.0


def test_patch_name_and_price(client, make_item):
    item = make_item("old", 10.0)
    resp = client.patch(f"/item/{item['id']}", json={"name": "n", "price": 1.0})
    assert resp.json()["name"] == "n"
    assert resp.json()["price"] == 1.0


def test_patch_missing_item_returns_304(client):
    assert client.patch("/item/999", json={"name": "x"}).status_code == 304


def test_patch_deleted_item_returns_304(client, make_item):
    item = make_item()
    client.delete(f"/item/{item['id']}")
    assert client.patch(f"/item/{item['id']}", json={"name": "x"}).status_code == 304


def test_patch_deleted_field_is_rejected(client, make_item):
    item = make_item()
    resp = client.patch(f"/item/{item['id']}", json={"deleted": True})
    assert resp.status_code == 422


def test_patch_unknown_field_is_rejected(client, make_item):
    item = make_item()
    resp = client.patch(f"/item/{item['id']}", json={"color": "red"})
    assert resp.status_code == 422


def test_delete_item_is_soft_and_idempotent(client, make_item):
    item = make_item()

    first = client.delete(f"/item/{item['id']}")
    assert first.status_code == 200
    assert first.json()["deleted"] is True

    second = client.delete(f"/item/{item['id']}")
    assert second.status_code == 200
    assert second.json()["deleted"] is True


def test_delete_missing_item(client):
    assert client.delete("/item/999").status_code == 404