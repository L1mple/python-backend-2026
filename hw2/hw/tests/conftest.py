from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from shop_api import database, main
from shop_api.chat import ChatRooms
from sqlalchemy import Engine


@pytest.fixture(autouse=True)
def isolated_state(
    monkeypatch: pytest.MonkeyPatch,
    database_factory: Callable[[Path], AbstractContextManager[Engine]],
    tmp_path: Path,
) -> Iterator[None]:
    """Keep our tests independent of each other and the instructor's fixtures."""
    with database_factory(tmp_path) as engine:
        monkeypatch.setattr(database, "engine", engine)
        monkeypatch.setattr(main, "chat_rooms", ChatRooms())
        yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(main.app) as test_client:
        yield test_client
