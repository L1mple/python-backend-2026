from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL

from shop_api.database import make_database_url
from shop_api.main import app

client = TestClient(app)


def test_missing_resources() -> None:
    missing_id = 1_000_000
    cart_id = client.post("/cart").json()["id"]

    assert client.get(f"/cart/{missing_id}").status_code == HTTPStatus.NOT_FOUND
    assert (
        client.post(f"/cart/{cart_id}/add/{missing_id}").status_code
        == HTTPStatus.NOT_FOUND
    )
    assert client.put(
        f"/item/{missing_id}",
        json={"name": "test item", "price": 10.0},
    ).status_code == HTTPStatus.NOT_FOUND
    assert client.patch(
        f"/item/{missing_id}",
        json={"price": 10.0},
    ).status_code == HTTPStatus.NOT_FOUND
    assert client.delete(f"/item/{missing_id}").status_code == HTTPStatus.NOT_FOUND


def test_deleted_item_cannot_be_changed_or_added_to_cart() -> None:
    item_id = client.post(
        "/item",
        json={"name": "test item", "price": 10.0},
    ).json()["id"]
    cart_id = client.post("/cart").json()["id"]

    assert client.delete(f"/item/{item_id}").status_code == HTTPStatus.OK
    assert client.put(
        f"/item/{item_id}",
        json={"name": "new name", "price": 20.0},
    ).status_code == HTTPStatus.NOT_MODIFIED
    assert client.patch(
        f"/item/{item_id}",
        json={"price": 20.0},
    ).status_code == HTTPStatus.NOT_MODIFIED
    assert (
        client.post(f"/cart/{cart_id}/add/{item_id}").status_code
        == HTTPStatus.NOT_FOUND
    )


def test_make_database_url_defaults_to_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_HOST", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert make_database_url() == "sqlite:///./db.sqlite3"


def test_make_database_url_for_sql_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_HOST", "database")
    monkeypatch.setenv("DATABASE_USER", "test-user")
    monkeypatch.setenv("DATABASE_PASSWORD", "test-password")
    monkeypatch.setenv("DATABASE_PORT", "1433")
    monkeypatch.setenv("DATABASE_NAME", "shop")

    database_url = make_database_url()

    assert isinstance(database_url, URL)
    assert database_url.drivername == "mssql+pymssql"
    assert database_url.username == "test-user"
    assert database_url.password == "test-password"
    assert database_url.host == "database"
    assert database_url.port == 1433
    assert database_url.database == "shop"


def test_make_database_url_requires_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_HOST", "database")
    monkeypatch.delenv("DATABASE_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_PASSWORD is required"):
        make_database_url()
