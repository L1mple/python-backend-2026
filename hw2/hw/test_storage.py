from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from shop_api import database
from shop_api.database import CartItemRow, CartRow, ItemRow
from shop_api.main import app
from shop_api.models import ItemData
from shop_api.store import Store
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture()
def api():
    with TestClient(app) as client:
        yield client


def test_data_survives_new_connections(api):
    item = api.post("/item", json={"name": uuid4().hex, "price": 19.99}).json()
    cart_id = api.post("/cart").json()["id"]
    assert api.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 200
    database.engine.dispose()
    assert api.get(f"/item/{item['id']}").json() == item
    cart = api.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["id"] == item["id"]
    assert cart["price"] == 19.99


def test_transaction_rolls_back(test_database):
    name = uuid4().hex
    with (
        pytest.raises(RuntimeError),
        Session(test_database) as session,
        session.begin(),
    ):
        Store(session).create_item(ItemData(name=name, price=1.0))
        raise RuntimeError("Abort transaction")
    with Session(test_database) as session:
        assert session.scalar(select(ItemRow).where(ItemRow.name == name)) is None


def test_cart_constraints_roll_back_whole_transaction(test_database):
    with Session(test_database) as session:
        before = session.scalar(select(func.count()).select_from(CartRow))
    with (
        pytest.raises(IntegrityError),
        Session(test_database) as session,
        session.begin(),
    ):
        cart = CartRow()
        session.add(cart)
        session.flush()
        session.add(CartItemRow(cart_id=cart.id, item_id=-1, quantity=1))
    with Session(test_database) as session:
        assert session.scalar(select(func.count()).select_from(CartRow)) == before


def test_concurrent_additions_are_not_lost(api):
    item_id = api.post("/item", json={"name": uuid4().hex, "price": 2.5}).json()["id"]
    cart_id = api.post("/cart").json()["id"]
    path = f"/cart/{cart_id}/add/{item_id}"
    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(lambda _: api.post(path), range(32)))
    assert all(response.status_code == 200 for response in responses)
    cart = api.get(f"/cart/{cart_id}").json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 32
    assert cart["price"] == 80.0


def test_concurrent_patches_preserve_both_fields(api):
    item_id = api.post("/item", json={"name": uuid4().hex, "price": 2.5}).json()["id"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda body: api.patch(f"/item/{item_id}", json=body),
                [{"name": "changed"}, {"price": 7.5}],
            )
        )
    assert all(response.status_code == 200 for response in responses)
    assert api.get(f"/item/{item_id}").json() == {
        "id": item_id,
        "name": "changed",
        "price": 7.5,
        "deleted": False,
    }


def test_deleted_item_is_excluded_from_price_but_not_quantity(api):
    item_id = api.post("/item", json={"name": uuid4().hex, "price": 7.5}).json()["id"]
    cart_id = api.post("/cart").json()["id"]
    for _ in range(2):
        api.post(f"/cart/{cart_id}/add/{item_id}")
    api.delete(f"/item/{item_id}")
    cart = api.get(f"/cart/{cart_id}").json()
    assert cart["price"] == 0.0
    assert cart["items"][0]["available"] is False
    assert cart["items"][0]["quantity"] == 2
    filtered = api.get(
        "/cart", params={"min_quantity": 2, "max_price": 0, "limit": 1000}
    ).json()
    assert cart in filtered
    assert api.post(f"/cart/{cart_id}/add/{item_id}").status_code == 404
    assert api.patch(f"/item/{item_id}", json={"name": "changed"}).status_code == 304
    assert api.get(f"/cart/{cart_id}").json() == cart


def test_replacement_restores_deleted_item(api):
    item_id = api.post("/item", json={"name": uuid4().hex, "price": 7.5}).json()["id"]
    cart_id = api.post("/cart").json()["id"]
    api.post(f"/cart/{cart_id}/add/{item_id}")
    api.delete(f"/item/{item_id}")
    response = api.put(f"/item/{item_id}", json={"name": "restored", "price": 10.0})
    assert response.status_code == 200
    cart = api.get(f"/cart/{cart_id}").json()
    assert cart["price"] == 10.0
    assert cart["items"][0]["name"] == "restored"
    assert cart["items"][0]["available"] is True


def test_cart_filtering_precedes_pagination(api):
    item_id = api.post("/item", json={"name": uuid4().hex, "price": 10001.0}).json()[
        "id"
    ]
    ids = [api.post("/cart").json()["id"] for _ in range(3)]
    for quantity, cart_id in enumerate(ids, start=1):
        for _ in range(quantity):
            api.post(f"/cart/{cart_id}/add/{item_id}")
    response = api.get("/cart", params={"min_price": 20002, "offset": 1, "limit": 1})
    assert response.status_code == 200
    assert [cart["id"] for cart in response.json()] == [ids[2]]


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/item/-1"),
        ("put", "/item/-1"),
        ("patch", "/item/-1"),
        ("delete", "/item/-1"),
        ("get", "/cart/-1"),
        ("post", "/cart/-1/add/-1"),
    ],
)
def test_missing_resources(api, method, path):
    kwargs = (
        {"json": {"name": "missing", "price": 1}} if method in {"put", "patch"} else {}
    )
    assert getattr(api, method)(path, **kwargs).status_code == 404


def test_http_exception_rolls_back(api, test_database, monkeypatch):
    name = uuid4().hex
    create_item = Store.create_item

    def failing_create(store, data):
        create_item(store, data)
        raise RuntimeError("Abort HTTP request")

    monkeypatch.setattr(Store, "create_item", failing_create)
    with pytest.raises(RuntimeError, match="Abort HTTP request"):
        api.post("/item", json={"name": name, "price": 3.0})
    with Session(test_database) as session:
        assert session.scalar(select(ItemRow).where(ItemRow.name == name)) is None


@pytest.mark.parametrize("method", ["delete", "put"])
def test_addition_during_item_deletion(api, method):
    item_id = api.post("/item", json={"name": uuid4().hex, "price": 3.0}).json()["id"]
    cart_id = api.post("/cart").json()["id"]
    barrier = Barrier(2)

    def add():
        barrier.wait(timeout=5)
        return api.post(f"/cart/{cart_id}/add/{item_id}")

    def remove():
        barrier.wait(timeout=5)
        if method == "delete":
            return api.delete(f"/item/{item_id}")
        return api.put(
            f"/item/{item_id}", json={"name": "removed", "price": 5, "deleted": True}
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        addition = executor.submit(add)
        deletion = executor.submit(remove)
        add_response = addition.result(timeout=10)
        delete_response = deletion.result(timeout=10)
    assert delete_response.status_code == 200
    assert add_response.status_code in {200, 404}
    cart = api.get(f"/cart/{cart_id}").json()
    assert cart["price"] == 0.0
    if add_response.status_code == 200:
        assert len(cart["items"]) == 1
        assert cart["items"][0]["quantity"] == 1
        assert cart["items"][0]["available"] is False
    else:
        assert cart["items"] == []
