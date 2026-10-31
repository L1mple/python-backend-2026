import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from hw2.hw.shop_api import db, main


@pytest.fixture(scope="session")
def database_engine():
    url = os.getenv("TEST_DATABASE_URL")
    if not url or make_url(url).get_backend_name() != "postgresql":
        raise pytest.UsageError("Need PostgreSQL database")

    schema = f"hw5_test_{uuid4().hex}"
    admin_engine = create_engine(url)
    test_engine = create_engine(
        url,
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
        db.Base.metadata.create_all(test_engine)
        yield test_engine
    finally:
        test_engine.dispose()
        try:
            with admin_engine.begin() as connection:
                connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        finally:
            admin_engine.dispose()


@pytest.fixture(autouse=True)
def empty_database(database_engine):
    with database_engine.begin() as connection:
        for table in reversed(db.Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture()
def client(database_engine, monkeypatch):
    monkeypatch.setattr(db, "engine", database_engine)
    monkeypatch.setattr(main, "engine", database_engine)
    monkeypatch.setattr(
        db,
        "SessionLocal",
        sessionmaker(bind=database_engine, expire_on_commit=False),
    )
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def item_data():
    return {"name": "Test item", "price": 12.5}


@pytest.fixture()
def create_item(client):
    def create(name="Test item", price=10.0):
        response = client.post("/item", json={"name": name, "price": price})
        assert response.status_code == 201
        return response.json()

    return create


@pytest.fixture()
def item(create_item, item_data):
    return create_item(**item_data)


@pytest.fixture()
def create_cart(client):
    def create():
        response = client.post("/cart")
        assert response.status_code == 201
        return response.json()

    return create


@pytest.fixture()
def cart(create_cart):
    return create_cart()


@pytest.fixture()
def add_to_cart(client):
    def add(cart_id, item_id, quantity=1):
        for _ in range(quantity):
            response = client.post(f"/cart/{cart_id}/add/{item_id}")
            assert response.status_code == 200
        return response.json()

    return add