import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://shop:shop@localhost:5432/shop_test"
)

from shop_api import models  # noqa: E402,F401  (регистрирует таблицы в Base.metadata)
from shop_api.db import Base, engine  # noqa: E402


def pytest_sessionstart(session):
    """Перед прогоном: пустые таблицы в тестовой базе."""
    assert engine.url.database.endswith("_test"), (
        f"Тесты удаляют таблицы, а база {engine.url.database!r} не тестовая"
    )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
