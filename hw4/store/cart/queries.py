from __future__ import annotations

from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from store.cart.models import CartEntity, CartItemEntity, CartItemOrm, CartOrm
from store.db import SessionLocal
from store.item.models import ItemOrm


def _load(session: Session, cart_ids: list[int]) -> list[CartEntity]:
    carts = {cart_id: CartEntity(id=cart_id) for cart_id in cart_ids}
    rows = session.execute(
        select(CartItemOrm.cart_id, CartItemOrm.quantity, ItemOrm)
        .join(ItemOrm, ItemOrm.id == CartItemOrm.item_id)
        .where(CartItemOrm.cart_id.in_(cart_ids))
        .order_by(ItemOrm.id)
    )
    for cart_id, quantity, item in rows:
        cart = carts[cart_id]
        cart.items.append(
            CartItemEntity(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        cart.price += item.price * quantity
    return list(carts.values())


def add() -> CartEntity:
    with SessionLocal.begin() as session:
        cart = CartOrm()
        session.add(cart)
        session.flush()
        return CartEntity(id=cart.id)


def get(cart_id: int) -> CartEntity | None:
    with SessionLocal() as session:
        if session.get(CartOrm, cart_id) is None:
            return None
        return _load(session, [cart_id])[0]


def add_item(cart_id: int, item_id: int) -> CartEntity | None:
    with SessionLocal.begin() as session:
        if session.get(CartOrm, cart_id) is None or session.get(ItemOrm, item_id) is None:
            return None
        stmt = insert(CartItemOrm).values(cart_id=cart_id, item_id=item_id, quantity=1)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=[CartItemOrm.cart_id, CartItemOrm.item_id],
                set_={"quantity": CartItemOrm.quantity + 1},
            )
        )
        return _load(session, [cart_id])[0]


def get_many(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> Iterable[CartEntity]:
    price = func.coalesce(func.sum(ItemOrm.price * CartItemOrm.quantity), 0)
    quantity = func.coalesce(func.sum(CartItemOrm.quantity), 0)
    query = (
        select(CartOrm.id)
        .outerjoin(CartItemOrm)
        .outerjoin(ItemOrm)
        .group_by(CartOrm.id)
    )
    if min_price is not None:
        query = query.having(price >= min_price)
    if max_price is not None:
        query = query.having(price <= max_price)
    if min_quantity is not None:
        query = query.having(quantity >= min_quantity)
    if max_quantity is not None:
        query = query.having(quantity <= max_quantity)
    query = query.order_by(CartOrm.id).offset(offset).limit(limit)

    with SessionLocal() as session:
        return _load(session, list(session.scalars(query)))
