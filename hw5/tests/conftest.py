from collections.abc import Callable, Iterator
from typing import Any
from uuid import uuid4

import pytest
from faker import Faker
from fastapi.testclient import TestClient
from shop_api.db import Base, engine
from shop_api.main import app

faker = Faker()


@pytest.fixture(scope="session", autouse=True)
def clean_db() -> Iterator[None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def create_item(client: TestClient) -> Callable[[], dict[str, Any]]:
    def _create_item() -> dict[str, Any]:
        return client.post(
            "/item",
            json={
                "name": f"item {uuid4().hex}",
                "price": faker.pyfloat(min_value=10.0, max_value=100.0, right_digits=2),
            },
        ).json()

    return _create_item


@pytest.fixture()
def item(create_item: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    return create_item()


@pytest.fixture()
def another_item(create_item: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    return create_item()


@pytest.fixture()
def deleted_item(client: TestClient, item: dict[str, Any]) -> dict[str, Any]:
    client.delete(f"/item/{item['id']}")
    return {**item, "deleted": True}


@pytest.fixture()
def cart_id(client: TestClient) -> int:
    return client.post("/cart").json()["id"]
