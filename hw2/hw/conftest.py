import pytest
from shop_api.database import init_db_sync


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db_sync()
    yield