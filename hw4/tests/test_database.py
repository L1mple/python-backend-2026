"""Тесты подключения к БД: ожидание старта и жизненный цикл сессии."""

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from shop_api import database


def fake_operational_error() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("the database system is starting up"))


def test_init_db_waits_until_database_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def flaky_create_all(bind) -> None:
        calls.append(1)
        if len(calls) < 3:
            raise fake_operational_error()

    monkeypatch.setattr(database.Base.metadata, "create_all", flaky_create_all)
    monkeypatch.setattr(database.time, "sleep", sleeps.append)

    database.init_db(attempts=5, delay=0.5)

    assert len(calls) == 3  # две неудачи и успех
    assert sleeps == [0.5, 0.5]


def test_init_db_gives_up_after_last_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def always_failing(bind) -> None:
        calls.append(1)
        raise fake_operational_error()

    monkeypatch.setattr(database.Base.metadata, "create_all", always_failing)
    monkeypatch.setattr(database.time, "sleep", lambda seconds: None)

    with pytest.raises(OperationalError):
        database.init_db(attempts=3, delay=0)

    assert len(calls) == 3


def test_get_session_yields_working_session_and_closes_it() -> None:
    generator = database.get_session()

    session = next(generator)

    assert isinstance(session, Session)
    assert session.connection().exec_driver_sql("SELECT 1").scalar() == 1
    generator.close()
    assert session.in_transaction() is False
