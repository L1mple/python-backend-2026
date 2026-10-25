import os

import pytest
from fastapi.testclient import TestClient


def pytest_configure(config):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    config.add_cleanup(monkeypatch.undo)


@pytest.fixture
def app(tmp_path):
    from shop_api.database import Base
    from shop_api.main import create_app

    database_url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'shop.sqlite3'}"
    application = create_app(database_url)
    engine = application.state.engine

    def clear_database():
        with engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())

    try:
        clear_database()
        yield application
    finally:
        try:
            clear_database()
        finally:
            engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
