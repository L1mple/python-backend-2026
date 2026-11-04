"""Прогон сценариев из isolation/demo.py: проверяем, что БД ведет себя так, как мы описали.

PostgreSQL берется из DATABASE_URL (в CI он есть всегда). MySQL проверяется, только если
задана переменная ISOLATION_MYSQL_URL (локально: mysql+pymysql://shop:shop@localhost:3307/shop).
"""

import os

import pytest
from sqlalchemy import create_engine

from isolation import demo
from shop_api.database import DATABASE_URL


@pytest.mark.skipif(not DATABASE_URL.startswith("postgresql"), reason="нужна PostgreSQL")
def test_isolation_levels_on_postgres(capsys: pytest.CaptureFixture[str]) -> None:
    assert demo.run_scenarios(create_engine(DATABASE_URL), "postgres"), capsys.readouterr().out


@pytest.mark.skipif("ISOLATION_MYSQL_URL" not in os.environ, reason="MySQL не настроен (ISOLATION_MYSQL_URL)")
def test_isolation_levels_on_mysql(capsys: pytest.CaptureFixture[str]) -> None:
    assert demo.run_scenarios(create_engine(os.environ["ISOLATION_MYSQL_URL"]), "mysql"), capsys.readouterr().out
