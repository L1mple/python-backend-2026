"""
Юнит-тесты для слоя работы с БД (crud.py).
Покрывают ветки, которые не задействованы в API-тестах HW2.
Используют in-memory SQLite для изоляции от Postgres.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shop_api import crud
from shop_api.database import Base


@pytest.fixture()
def db():
    """Изолированная in-memory SQLite-сессия на каждый тест."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ==================== ITEM ====================

def test_create_item(db):
    item = crud.create_item(db, name="Test", price=10.5)
    assert item["name"] == "Test"
    assert item["price"] == 10.5
    assert item["deleted"] is False


def test_get_item(db):
    created = crud.create_item(db, name="Test", price=10.5)
    fetched = crud.get_item(db, created["id"])
    assert fetched == created


def test_get_item_not_found(db):
    assert crud.get_item(db, 999) is None


def test_list_items(db):
    crud.create_item(db, name="A", price=10)
    crud.create_item(db, name="B", price=20)
    items = crud.list_items(
        db, offset=0, limit=10, min_price=None, max_price=None, show_deleted=False
    )
    assert len(items) == 2


def test_list_items_with_filters(db):
    crud.create_item(db, name="A", price=10)
    crud.create_item(db, name="B", price=20)
    items = crud.list_items(
        db, offset=0, limit=10, min_price=15, max_price=None, show_deleted=False
    )
    assert len(items) == 1
    assert items[0]["name"] == "B"


def test_list_items_show_deleted(db):
    item = crud.create_item(db, name="A", price=10)
    crud.mark_item_deleted(db, item["id"])
    hidden = crud.list_items(
        db, offset=0, limit=10, min_price=None, max_price=None, show_deleted=False
    )
    visible = crud.list_items(
        db, offset=0, limit=10, min_price=None, max_price=None, show_deleted=True
    )
    assert len(hidden) == 0
    assert len(visible) == 1


def test_list_items_offset_limit(db):
    for i in range(5):
        crud.create_item(db, name=f"Item{i}", price=10 + i)
    items = crud.list_items(
        db, offset=2, limit=2, min_price=None, max_price=None, show_deleted=False
    )
    assert len(items) == 2


def test_replace_item(db):
    item = crud.create_item(db, name="A", price=10)
    updated = crud.replace_item(db, item["id"], name="B", price=20)
    assert updated["name"] == "B"
    assert updated["price"] == 20


def test_replace_item_not_found(db):
    assert crud.replace_item(db, 999, name="B", price=20) is None


def test_replace_deleted_item(db):
    item = crud.create_item(db, name="A", price=10)
    crud.mark_item_deleted(db, item["id"])
    assert crud.replace_item(db, item["id"], name="B", price=20) is None


def test_patch_item_name_only(db):
    item = crud.create_item(db, name="A", price=10)
    updated = crud.patch_item(db, item["id"], name="B", price=None)
    assert updated["name"] == "B"
    assert updated["price"] == 10


def test_patch_item_price_only(db):
    item = crud.create_item(db, name="A", price=10)
    updated = crud.patch_item(db, item["id"], name=None, price=99)
    assert updated["name"] == "A"
    assert updated["price"] == 99


def test_patch_item_not_found(db):
    assert crud.patch_item(db, 999, name="B", price=None) is None


def test_patch_deleted_item(db):
    item = crud.create_item(db, name="A", price=10)
    crud.mark_item_deleted(db, item["id"])
    assert crud.patch_item(db, item["id"], name="B", price=None) is None


def test_mark_item_deleted(db):
    item = crud.create_item(db, name="A", price=10)
    assert crud.mark_item_deleted(db, item["id"]) is True
    assert crud.get_item(db, item["id"])["deleted"] is True


def test_mark_item_deleted_not_found(db):
    assert crud.mark_item_deleted(db, 999) is False


# ==================== CART ====================

def test_create_cart(db):
    cart_id = crud.create_cart(db)
    assert cart_id > 0


def test_get_cart_contents(db):
    cart_id = crud.create_cart(db)
    item = crud.create_item(db, name="A", price=10)
    crud.add_item_to_cart(db, cart_id, item["id"])
    contents = crud.get_cart_contents(db, cart_id)
    assert contents == {item["id"]: 1}


def test_get_cart_contents_not_found(db):
    assert crud.get_cart_contents(db, 999) is None


def test_add_item_to_cart_existing(db):
    cart_id = crud.create_cart(db)
    item = crud.create_item(db, name="A", price=10)
    crud.add_item_to_cart(db, cart_id, item["id"])
    crud.add_item_to_cart(db, cart_id, item["id"])
    contents = crud.get_cart_contents(db, cart_id)
    assert contents == {item["id"]: 2}


def test_cart_price(db):
    cart_id = crud.create_cart(db)
    item = crud.create_item(db, name="A", price=10)
    crud.add_item_to_cart(db, cart_id, item["id"])
    assert crud.cart_price(db, cart_id) == 10


def test_cart_quantity(db):
    cart_id = crud.create_cart(db)
    item = crud.create_item(db, name="A", price=10)
    crud.add_item_to_cart(db, cart_id, item["id"])
    assert crud.cart_quantity(db, cart_id) == 1


def test_list_carts(db):
    cart_id = crud.create_cart(db)
    item = crud.create_item(db, name="A", price=10)
    crud.add_item_to_cart(db, cart_id, item["id"])
    carts = crud.list_carts(
        db,
        offset=0,
        limit=10,
        min_price=5,
        max_price=20,
        min_quantity=1,
        max_quantity=5,
    )
    assert len(carts) == 1
    assert carts[0] == cart_id


def test_list_carts_filters_out(db):
    cart_id = crud.create_cart(db)
    item = crud.create_item(db, name="A", price=100)
    crud.add_item_to_cart(db, cart_id, item["id"])
    carts = crud.list_carts(
        db,
        offset=0,
        limit=10,
        min_price=None,
        max_price=50,
        min_quantity=None,
        max_quantity=None,
    )
    assert len(carts) == 0
