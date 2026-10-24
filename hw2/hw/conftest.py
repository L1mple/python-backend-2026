import atexit
import os
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

if "DATABASE_URL" not in os.environ:
    database_directory = TemporaryDirectory(prefix="shop-tests-")
    os.environ["DATABASE_URL"] = f"sqlite:///{database_directory.name}/shop.db"
    atexit.register(database_directory.cleanup)


@pytest.fixture
def isolated_shop(tmp_path):
    from shop_api.store import Shop

    engine = create_engine(os.environ["DATABASE_URL"])
    schema = None
    if engine.dialect.name == "postgresql":
        schema = f"test_{uuid4().hex}"
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    else:
        url = f"sqlite:///{tmp_path / 'shop.db'}"
    shop = Shop(url)
    try:
        yield shop
    finally:
        shop.engine.dispose()
        if schema:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
