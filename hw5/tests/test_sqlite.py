import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from shop_api.database import Base, CartItemRow, CartRow, ItemRow, make_engine


def test_sqlite_fallback_persists_data_and_enforces_foreign_keys(tmp_path):
    url = f"sqlite:///{tmp_path / 'shop.db'}"
    engine = make_engine(url)
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            item_id = connection.execute(insert(ItemRow).values(
                name="Bread", price=5, deleted=False,
            )).inserted_primary_key[0]
            cart_id = connection.execute(insert(CartRow)).inserted_primary_key[0]
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(insert(CartItemRow).values(
                    cart_id=cart_id, item_id=-1, quantity=1,
                ))
        with engine.begin() as connection:
            connection.execute(insert(CartItemRow).values(
                cart_id=cart_id, item_id=item_id, quantity=2,
            ))
    finally:
        engine.dispose()

    reopened = make_engine(url)
    try:
        with reopened.connect() as connection:
            assert connection.scalar(select(ItemRow.name)) == "Bread"
            assert connection.scalar(select(CartItemRow.quantity)) == 2
            # Check a new connection too, not only the one that created the schema.
            with pytest.raises(IntegrityError):
                connection.execute(insert(CartItemRow).values(
                    cart_id=-1, item_id=item_id, quantity=1,
                ))
    finally:
        reopened.dispose()
