from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite://"

from hw.shop_api import main


@pytest.fixture()
def client():
    main.Base.metadata.drop_all(main.engine)
    main.Base.metadata.create_all(main.engine)
    main.chat_clients.clear()
    main.user_ids = 0
    with TestClient(main.app) as test_client:
        yield test_client
    main.chat_clients.clear()


@pytest.fixture()
def session(client):
    with main.SessionLocal() as database_session:
        yield database_session
