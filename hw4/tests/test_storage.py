import json
import os
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from shop_api import database
from shop_api.database import create_db_engine, get_session
from shop_api.main import app
from shop_api.models import Base, CartLine, ItemRow
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session


@pytest.fixture()
def db_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'shop.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine: Engine) -> Iterator[TestClient]:
    def session_override() -> Iterator[Session]:
        with Session(db_engine) as session, session.begin():
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session)


def test_cart_uses_current_prices_and_keeps_deleted_items(client: TestClient) -> None:
    item = client.post("/item", json={"name": "Milk", "price": 10}).json()
    cart_id = client.post("/cart").json()["id"]
    path = f"/cart/{cart_id}/add/{item['id']}"
    assert client.post(path).status_code == 200
    assert client.post(path).json()["price"] == 20
    assert client.patch(f"/item/{item['id']}", json={"price": 25}).status_code == 200
    assert client.get(f"/cart/{cart_id}").json()["price"] == 50
    client.delete(f"/item/{item['id']}")
    result = client.get(f"/cart/{cart_id}").json()
    assert result["items"] == [
        {"id": item["id"], "name": "Milk", "quantity": 2, "available": False}
    ]
    assert result["price"] == 50
    assert client.post(path).status_code == 404
    assert client.get(f"/cart/{cart_id}").json() == result


def test_cart_filters_and_pagination_include_empty_carts(client: TestClient) -> None:
    empty_id = client.post("/cart").json()["id"]
    full_id = client.post("/cart").json()["id"]
    item_id = client.post("/item", json={"name": "Bread", "price": 12}).json()["id"]
    client.post(f"/cart/{full_id}/add/{item_id}")
    assert [cart["id"] for cart in client.get("/cart?max_quantity=0").json()] == [
        empty_id
    ]
    assert [
        cart["id"] for cart in client.get("/cart?min_price=12&max_price=12").json()
    ] == [full_id]
    assert [cart["id"] for cart in client.get("/cart?offset=1&limit=1").json()] == [
        full_id
    ]


def test_concurrent_additions_do_not_lose_quantity(
    client: TestClient, db_engine: Engine
) -> None:
    item_id = client.post("/item", json={"name": "Tea", "price": 3}).json()["id"]
    cart_id = client.post("/cart").json()["id"]
    with ThreadPoolExecutor(max_workers=4) as workers:
        responses = list(
            workers.map(
                lambda _: client.post(f"/cart/{cart_id}/add/{item_id}"), range(24)
            )
        )
    assert all(response.status_code == 200 for response in responses)
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["quantity"] == 24
    assert cart["price"] == 72
    with Session(db_engine) as session:
        assert session.scalar(select(func.count()).select_from(CartLine)) == 1


def test_dependency_rolls_back_failed_transaction(
    db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(database, "get_engine", lambda: db_engine)
    with (
        pytest.raises(ValueError, match="abort"),
        contextmanager(get_session)() as session,
    ):
        session.add(ItemRow(name="Rolled back", price=10))
        session.flush()
        raise ValueError("abort")
    with Session(db_engine) as session:
        assert session.scalar(select(func.count()).select_from(ItemRow)) == 0


def test_sqlite_data_survives_new_process(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'persistent.db'}"
    env["PYTHONPATH"] = (
        str(Path(__file__).resolve().parents[2] / "hw2/hw")
        + os.pathsep
        + env.get("PYTHONPATH", "")
    )
    write = """import json
from fastapi.testclient import TestClient
from shop_api.main import app
with TestClient(app) as client:
 item=client.post('/item',json={'name':'Persistent','price':7}).json()
 cart=client.post('/cart').json()
 client.post(f"/cart/{cart['id']}/add/{item['id']}")
 client.delete(f"/item/{item['id']}")
 print(json.dumps({'item_id':item['id'],'cart_id':cart['id']}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", write],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    ids = json.loads(completed.stdout)
    read = """import json,sys
from fastapi.testclient import TestClient
from shop_api.main import app
ids=json.loads(sys.argv[1])
with TestClient(app) as client:
 cart=client.get(f"/cart/{ids['cart_id']}").json()
 assert cart['price']==7
 assert cart['items'][0]['name']=='Persistent'
 assert cart['items'][0]['available'] is False
 assert client.get(f"/item/{ids['item_id']}").status_code==404
"""
    subprocess.run(
        [sys.executable, "-c", read, json.dumps(ids)],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
