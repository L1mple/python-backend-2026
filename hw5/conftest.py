from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from shop_api.database import CartLine, CartRow, ItemRow, engine, get_session
from shop_api.main import app


@pytest.fixture
def client():
    with engine.connect() as connection:
        transaction = connection.begin()
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN")
        try:
            for table in (CartLine, CartRow, ItemRow):
                connection.execute(delete(table))

            def test_session():
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    with session.begin():
                        yield session

            app.dependency_overrides[get_session] = test_session
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
