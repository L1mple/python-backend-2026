import os

import pytest


# Тесты используют отдельную БД и не удаляют данные локально запущенного магазина.
os.environ.setdefault("SHOP_DATABASE_URL", "sqlite:///:memory:")

from shop_api.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
