import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    config.shop_original_database_url = os.environ.get("DATABASE_URL")
    config.shop_test_directory = TemporaryDirectory(prefix="shop-api-tests-")
    database_path = Path(config.shop_test_directory.name) / "shop.db"
    os.environ["DATABASE_URL"] = os.getenv(
        "TEST_DATABASE_URL", f"sqlite:///{database_path}"
    )


def pytest_unconfigure(config):
    from shop_api.database import engine

    engine.dispose()
    config.shop_test_directory.cleanup()
    original_url = config.shop_original_database_url
    if original_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_url


@pytest.fixture
def client():
    from shop_api.main import app

    with TestClient(app) as test_client:
        yield test_client
