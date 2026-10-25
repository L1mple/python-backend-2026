from typing import Iterable

from sqlmodel import select

from .database import get_session
from .db_models import CartDB, CartItemDB, ItemDB
from .models import Cart, Item


def add_item(name: str, price: float) -> Item:
    with get_session() as session:
        item_db = ItemDB(
            name=name,
            price=price,
        )

        session.add(item_db)
        session.commit()
        session.refresh(item_db)

        return Item(
            id=item_db.id,
            name=item_db.name,
            price=item_db.price,
            deleted=item_db.deleted,
        )


def get_item(item_id: int) -> Item | None:
    with get_session() as session:
        item_db = session.get(ItemDB, item_id)

        if item_db is None:
            return None

        return Item(
            id=item_db.id,
            name=item_db.name,
            price=item_db.price,
            deleted=item_db.deleted,
        )


def get_all_items() -> Iterable[Item]:
    with get_session() as session:
        statement = select(ItemDB)
        items = session.exec(statement).all()

        return [
            Item(
                id=item.id,
                name=item.name,
                price=item.price,
                deleted=item.deleted,
            )
            for item in items
        ]


def update_item(
    item_id: int,
    name: str,
    price: float,
) -> Item | None:
    with get_session() as session:
        item_db = session.get(ItemDB, item_id)

        if item_db is None or item_db.deleted:
            return None

        item_db.name = name
        item_db.price = price

        session.add(item_db)
        session.commit()
        session.refresh(item_db)

        return Item(
            id=item_db.id,
            name=item_db.name,
            price=item_db.price,
            deleted=item_db.deleted,
        )


def patch_item(
    item_id: int,
    name: str | None = None,
    price: float | None = None,
) -> Item | None:
    with get_session() as session:
        item_db = session.get(ItemDB, item_id)

        if item_db is None or item_db.deleted:
            return None

        if name is not None:
            item_db.name = name

        if price is not None:
            item_db.price = price

        session.add(item_db)
        session.commit()
        session.refresh(item_db)

        return Item(
            id=item_db.id,
            name=item_db.name,
            price=item_db.price,
            deleted=item_db.deleted,
        )


def delete_item(item_id: int) -> None:
    with get_session() as session:
        item_db = session.get(ItemDB, item_id)

        if item_db is not None:
            item_db.deleted = True
            session.add(item_db)
            session.commit()


def add_cart() -> Cart:
    with get_session() as session:
        cart_db = CartDB()

        session.add(cart_db)
        session.commit()
        session.refresh(cart_db)

        return Cart(id=cart_db.id)


def get_cart(cart_id: int) -> Cart | None:
    with get_session() as session:
        cart_db = session.get(CartDB, cart_id)

        if cart_db is None:
            return None

        statement = select(CartItemDB).where(
            CartItemDB.cart_id == cart_id
        )

        cart_items = session.exec(statement).all()

        return Cart(
            id=cart_db.id,
            items={
                item.item_id: item.quantity
                for item in cart_items
            },
        )


def get_all_carts() -> Iterable[Cart]:
    with get_session() as session:
        carts = session.exec(select(CartDB)).all()

        result = []

        for cart_db in carts:
            statement = select(CartItemDB).where(
                CartItemDB.cart_id == cart_db.id
            )

            cart_items = session.exec(statement).all()

            result.append(
                Cart(
                    id=cart_db.id,
                    items={
                        item.item_id: item.quantity
                        for item in cart_items
                    },
                )
            )

        return result


def add_item_to_cart(
    cart_id: int,
    item_id: int,
) -> bool:
    with get_session() as session:
        cart_db = session.get(CartDB, cart_id)
        item_db = session.get(ItemDB, item_id)

        if cart_db is None or item_db is None or item_db.deleted:
            return False

        cart_item = session.get(
            CartItemDB,
            (cart_id, item_id),
        )

        if cart_item is None:
            cart_item = CartItemDB(
                cart_id=cart_id,
                item_id=item_id,
                quantity=1,
            )
        else:
            cart_item.quantity += 1

        session.add(cart_item)
        session.commit()

        return True