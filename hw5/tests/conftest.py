import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://shop:shop@localhost:5432/shop_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from shop_api.db import engine
from shop_api.main import app


def _ensure_database() -> None:
    """Создаёт тестовую БД, если её ещё нет (в CI она создаётся самим сервисом)."""
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": url.database},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def client():
    _ensure_database()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db(client):
    """Перед каждым тестом пустые таблицы и счётчики id начинаются с 1."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE cart_items, carts, items RESTART IDENTITY CASCADE"))


@pytest.fixture
def make_item(client):
    def _make(name: str = "item", price: float = 10.0) -> dict:
        resp = client.post("/item", json={"name": name, "price": price})
        assert resp.status_code == 201
        return resp.json()

    return _make


@pytest.fixture
def make_cart(client):
    def _make() -> int:
        resp = client.post("/cart")
        assert resp.status_code == 201
        return resp.json()["id"]

    return _make