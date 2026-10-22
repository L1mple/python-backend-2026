import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from faker import Faker
from fastapi.testclient import TestClient

from shop_api.main import app

faker = Faker()


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
