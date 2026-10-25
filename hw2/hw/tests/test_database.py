from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from shop_api.database import CartItemRecord, CartRecord, ItemRecord, create_database


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_database(f"sqlite:///{tmp_path / 'database.sqlite3'}")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.parametrize("database_url", ["sqlite://", "sqlite:///:memory:"])
def test_memory_database_retains_data_between_requests(database_url: str) -> None:
    from shop_api.main import create_app

    app = create_app(database_url)
    try:
        with TestClient(app) as client:
            response = client.post("/item", json={"name": "Memory item", "price": 0})
            assert response.status_code == 201
            item = response.json()
            response = client.get(f"/item/{item['id']}")
            assert response.status_code == 200
            assert response.json() == item
    finally:
        app.state.engine.dispose()


def test_database_url_from_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "environment.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")

    engine = create_database()
    try:
        assert path.is_file()
        with engine.connect() as connection:
            assert connection.execute(select(ItemRecord)).all() == []
    finally:
        engine.dispose()


def test_explicit_database_url_overrides_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment_path = tmp_path / "environment.sqlite3"
    explicit_path = tmp_path / "explicit.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{environment_path}")

    engine = create_database(f"sqlite:///{explicit_path}")
    try:
        assert explicit_path.is_file()
        assert not environment_path.exists()
    finally:
        engine.dispose()


def test_items_and_carts_persist_after_application_restart(tmp_path: Path) -> None:
    from shop_api.main import create_app

    database_url = f"sqlite:///{tmp_path / 'persistent.sqlite3'}"
    app = create_app(database_url)
    try:
        with TestClient(app) as client:
            response = client.post("/item", json={"name": "Apple", "price": 5.25})
            assert response.status_code == 201
            apple = response.json()
            response = client.post("/item", json={"name": "Berry", "price": 7})
            assert response.status_code == 201
            berry = response.json()
            response = client.post("/cart")
            assert response.status_code == 201
            cart_id = response.json()["id"]
            for item_id in [apple["id"], apple["id"], berry["id"]]:
                assert client.post(f"/cart/{cart_id}/add/{item_id}").status_code == 200
            assert client.delete(f"/item/{berry['id']}").status_code == 200
    finally:
        app.state.engine.dispose()

    reopened_app = create_app(database_url)
    try:
        with TestClient(reopened_app) as client:
            assert client.get("/item").json() == [apple]
            assert client.get("/item", params={"show_deleted": True}).json() == [
                apple,
                {**berry, "deleted": True},
            ]
            assert client.get(f"/item/{berry['id']}").status_code == 404
            response = client.get(f"/cart/{cart_id}")
            assert response.status_code == 200
            assert response.json() == {
                "id": cart_id,
                "items": [
                    {"id": apple["id"], "name": "Apple", "quantity": 2, "available": True},
                    {"id": berry["id"], "name": "Berry", "quantity": 1, "available": False},
                ],
                "price": 10.5,
            }
    finally:
        reopened_app.state.engine.dispose()


@pytest.mark.parametrize("price", [-1, -0.01])
def test_database_rejects_negative_item_price(sqlite_engine: Engine, price: float) -> None:
    with pytest.raises(IntegrityError):
        with sqlite_engine.begin() as connection:
            connection.execute(insert(ItemRecord).values(name="Invalid", price=price))

    with sqlite_engine.connect() as connection:
        assert connection.execute(select(ItemRecord)).all() == []


@pytest.mark.parametrize("quantity", [0, -1])
def test_database_rejects_nonpositive_quantity(sqlite_engine: Engine, quantity: int) -> None:
    with sqlite_engine.begin() as connection:
        connection.execute(insert(ItemRecord).values(id=1, name="Item", price=1))
        connection.execute(insert(CartRecord).values(id=1))

    with pytest.raises(IntegrityError):
        with sqlite_engine.begin() as connection:
            connection.execute(
                insert(CartItemRecord).values(cart_id=1, item_id=1, quantity=quantity)
            )

    with sqlite_engine.connect() as connection:
        assert connection.execute(select(CartItemRecord)).all() == []


@pytest.mark.parametrize(("cart_id", "item_id"), [(2, 1), (1, 2)])
def test_database_enforces_cart_item_foreign_keys(
    sqlite_engine: Engine, cart_id: int, item_id: int
) -> None:
    with sqlite_engine.begin() as connection:
        connection.execute(insert(ItemRecord).values(id=1, name="Item", price=1))
        connection.execute(insert(CartRecord).values(id=1))

    sqlite_engine.dispose()

    with pytest.raises(IntegrityError):
        with sqlite_engine.begin() as connection:
            connection.execute(
                insert(CartItemRecord).values(cart_id=cart_id, item_id=item_id, quantity=1)
            )

    with sqlite_engine.connect() as connection:
        assert connection.execute(select(CartItemRecord)).all() == []


def test_failed_transaction_rolls_back_all_its_writes(sqlite_engine: Engine) -> None:
    with pytest.raises(IntegrityError):
        with sqlite_engine.begin() as connection:
            connection.execute(insert(ItemRecord).values(name="Valid", price=10))
            connection.execute(insert(ItemRecord).values(name="Invalid", price=-1))

    with sqlite_engine.begin() as connection:
        assert connection.execute(select(ItemRecord)).all() == []
        connection.execute(insert(ItemRecord).values(name="After rollback", price=0))

    with sqlite_engine.connect() as connection:
        assert connection.execute(select(ItemRecord.name, ItemRecord.price)).all() == [
            ("After rollback", 0)
        ]
