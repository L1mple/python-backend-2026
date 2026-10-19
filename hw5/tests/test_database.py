from pathlib import Path

import pytest
from shop_api import database
from shop_api.models import Base, CartLine, ItemRow
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_in_memory_database_is_shared_between_sessions(url: str) -> None:
    engine = database.create_db_engine(url)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session, session.begin():
            session.add(ItemRow(name="Memory", price=7))
        with Session(engine) as session:
            item = session.scalar(select(ItemRow))
            assert item.name == "Memory" and item.price == 7
    finally:
        engine.dispose()


def test_sqlite_foreign_key_failure_rolls_back_transaction(tmp_path: Path) -> None:
    engine = database.create_db_engine(f"sqlite:///{tmp_path / 'constraints.db'}")
    try:
        Base.metadata.create_all(engine)
        with pytest.raises(IntegrityError), Session(engine) as session, session.begin():
            item = ItemRow(name="Rollback", price=5)
            session.add(item)
            session.flush()
            session.add(CartLine(cart_id=999, item_id=item.id, quantity=1))
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(ItemRow)) == 0
    finally:
        engine.dispose()


def test_default_database_is_a_cached_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database.get_engine().dispose()
    database.get_engine.cache_clear()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    try:
        engine = database.get_engine()
        assert database.get_engine() is engine
        assert (tmp_path / "shop.db").is_file()
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(ItemRow)) == 0
    finally:
        database.get_engine().dispose()
        database.get_engine.cache_clear()
