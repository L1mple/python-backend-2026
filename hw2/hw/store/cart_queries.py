
from typing import Iterable

from sqlalchemy import select

from .database import SessionLocal
from .models import CartEntity, CartInfo
from .orm_models import CartItemOrm, CartOrm


def add_cart() -> CartEntity:
    with SessionLocal.begin() as session:
        cart = CartOrm()

        session.add(cart)
        session.flush()

        return CartEntity(
            id=cart.id,
            info=CartInfo(),
        )


def get_cart(cart_id: int) -> CartEntity | None:
    with SessionLocal() as session:
        cart = session.get(CartOrm, cart_id)

        if cart is None:
            return None

        rows = session.scalars(
            select(CartItemOrm).where(
                CartItemOrm.cart_id == cart_id
            )
        ).all()

        items = {
            row.item_id: row.quantity
            for row in rows
        }

        return CartEntity(
            id=cart.id,
            info=CartInfo(items=items),
        )


def get_all_carts() -> Iterable[CartEntity]:
    with SessionLocal() as session:
        cart_ids = session.scalars(
            select(CartOrm.id).order_by(CartOrm.id)
        ).all()

        rows = session.scalars(
            select(CartItemOrm)
        ).all()

        items_by_cart = {
            cart_id: {}
            for cart_id in cart_ids
        }

        for row in rows:
            items_by_cart[row.cart_id][row.item_id] = (
                row.quantity
            )

        return [
            CartEntity(
                id=cart_id,
                info=CartInfo(
                    items=items_by_cart[cart_id]
                ),
            )
            for cart_id in cart_ids
        ]


def add_item_to_cart(
        cart_id: int,
        item_id: int,
) -> bool:
    with SessionLocal.begin() as session:
        cart = session.get(CartOrm, cart_id)

        if cart is None:
            return False

        cart_item = session.get(
            CartItemOrm,
            (cart_id, item_id),
        )

        if cart_item is None:
            cart_item = CartItemOrm(
                cart_id=cart_id,
                item_id=item_id,
                quantity=1,
            )
            session.add(cart_item)
        else:
            cart_item.quantity += 1

        return True
