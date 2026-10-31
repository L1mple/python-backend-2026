from fastapi import Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .db import get_session
from .models import Cart, CartItem, Item


def apply_bounds(statement, column, minimum, maximum):
    if minimum is not None:
        statement = statement.where(column >= minimum)
    if maximum is not None:
        statement = statement.where(column <= maximum)
    return statement


def item_response(item):
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }


class ShopRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, resource):
        self.session.add(resource)
        self.session.flush()
        return resource

    def get_item(self, item_id):
        return self.session.get(Item, item_id)

    def get_cart(self, cart_id, lock=False):
        statement = select(Cart).where(Cart.id == cart_id)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_items(self, offset, limit, min_price, max_price, show_deleted):
        statement = select(Item)
        if not show_deleted:
            statement = statement.where(Item.deleted.is_(False))
        statement = apply_bounds(statement, Item.price, min_price, max_price)
        statement = statement.order_by(Item.id).offset(offset).limit(limit)
        return [item_response(item) for item in self.session.scalars(statement)]

    def cart_responses(self, cart_ids):
        result = {
            cart_id: {"id": cart_id, "items": [], "price": 0.0}
            for cart_id in cart_ids
        }
        if not result:
            return []
        statement = (
            select(CartItem, Item)
            .join(Item, Item.id == CartItem.item_id)
            .where(CartItem.cart_id.in_(cart_ids))
            .order_by(CartItem.cart_id, CartItem.item_id)
        )
        for entry, item in self.session.execute(statement):
            cart = result[entry.cart_id]
            cart["items"].append({
                "id": item.id,
                "name": item.name,
                "quantity": entry.quantity,
                "available": not item.deleted,
            })
            if not item.deleted:
                cart["price"] += item.price * entry.quantity
        return list(result.values())

    def get_carts(self, offset, limit, min_price, max_price, min_quantity, max_quantity):
        totals = (
            select(
                Cart.id.label("id"),
                func.coalesce(func.sum(case(
                    (Item.deleted.is_(False), Item.price * CartItem.quantity),
                    else_=0.0,
                )), 0.0).label("price"),
                func.coalesce(func.sum(CartItem.quantity), 0).label("quantity"),
            )
            .select_from(Cart)
            .outerjoin(CartItem, Cart.id == CartItem.cart_id)
            .outerjoin(Item, CartItem.item_id == Item.id)
            .group_by(Cart.id)
            .subquery()
        )
        statement = select(totals.c.id)
        statement = apply_bounds(statement, totals.c.price, min_price, max_price)
        statement = apply_bounds(statement, totals.c.quantity, min_quantity, max_quantity)
        statement = statement.order_by(totals.c.id).offset(offset).limit(limit)
        return self.cart_responses(list(self.session.scalars(statement)))

    def add_item(self, cart_id, item_id):
        entry = self.session.get(CartItem, (cart_id, item_id))
        if entry is None:
            entry = CartItem(cart_id=cart_id, item_id=item_id, quantity=1)
        else:
            entry.quantity += 1
        self.save(entry)


def get_repository(session: Session = Depends(get_session)):
    return ShopRepository(session)