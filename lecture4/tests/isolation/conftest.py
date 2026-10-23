
import os

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def engine():
    url = os.getenv(
        "ISOLATION_TEST_DATABASE_URL",
        "mysql+pymysql://shop:shop_password@127.0.0.1:3306/isolation_lab",
    )
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS isolation_accounts (
                id INT PRIMARY KEY,
                balance INT NOT NULL
            ) ENGINE=InnoDB
        """))
        conn.execute(text("DELETE FROM isolation_accounts"))
        conn.execute(text("""
            INSERT INTO isolation_accounts (id, balance)
            VALUES (1, 100), (2, 200)
        """))

    yield engine
    engine.dispose()
