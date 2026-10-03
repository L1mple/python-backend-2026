from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from shop_api import main
from shop_api.chat import ChatRooms
from shop_api.store import ShopStore


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep our tests independent of each other and the instructor's fixtures."""
    monkeypatch.setattr(main, "store", ShopStore())
    monkeypatch.setattr(main, "chat_rooms", ChatRooms())


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(main.app) as test_client:
        yield test_client
