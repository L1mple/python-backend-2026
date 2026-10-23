import socket
from collections.abc import Iterator
import pytest
from shop_api.store import database


@pytest.fixture
def listening_port() -> Iterator[int]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        yield server.getsockname()[1]


@pytest.fixture
def closed_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return port


def test_postgres_listening_socket(
    monkeypatch: pytest.MonkeyPatch,
    listening_port: int,
) -> None:
    monkeypatch.setattr(database, "POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setattr(database, "POSTGRES_PORT", listening_port)
    assert database.postgres_is_reachable() is True


def test_postgres_closed_socket(
    monkeypatch: pytest.MonkeyPatch,
    closed_port: int,
) -> None:
    monkeypatch.setattr(database, "POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setattr(database, "POSTGRES_PORT", closed_port)
    assert database.postgres_is_reachable(timeout=0.2) is False


def test_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db:5432/shop")
    monkeypatch.setattr(database, "postgres_is_reachable", lambda *_, **__: False)
    assert (database.resolve_database_url() == "postgresql+asyncpg://user:pass@db:5432/shop")


def test_url_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "postgres_is_reachable", lambda *_, **__: True)
    assert database.resolve_database_url() == database.POSTGRES_URL


def test_url_sqlite_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "postgres_is_reachable", lambda *_, **__: False)
    assert database.resolve_database_url() == database.SQLITE_URL


def test_url_empty_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(database, "postgres_is_reachable", lambda *_, **__: False)
    assert database.resolve_database_url() == database.SQLITE_URL
