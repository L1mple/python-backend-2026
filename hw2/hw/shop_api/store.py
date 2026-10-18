from math import fsum, isfinite

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db_models import CartLineRecord, CartRecord, ItemRecord
from .models import Cart, CartItem, Item


class Store:
    @staticmethod
    def cart_price(cart: CartRecord, replacement: Item | None = None) -> float:
        prices = []
        for line in cart.lines:
            item = (
                replacement
                if replacement is not None and replacement.id == line.item_id
                else line.item
            )
            if not item.deleted:
                prices.append(item.price * line.quantity)
        price = fsum(prices)
        if not isfinite(price):
            raise OverflowError("Cart price is too large")
        return price

    @staticmethod
    def get_cart(session: Session, cart_id: int) -> CartRecord | None:
        return session.scalar(
            select(CartRecord)
            .where(CartRecord.id == cart_id)
            .options(selectinload(CartRecord.lines).selectinload(CartLineRecord.item))
        )

    @staticmethod
    def to_cart(cart: CartRecord) -> Cart:
        return Cart(
            id=cart.id,
            items=[
                CartItem(
                    id=line.item.id,
                    name=line.item.name,
                    quantity=line.quantity,
                    available=not line.item.deleted,
                )
                for line in cart.lines
            ],
            price=Store.cart_price(cart),
        )

    @staticmethod
    def add_to_cart(session: Session, cart: CartRecord, item: ItemRecord) -> None:
        line = next((line for line in cart.lines if line.item_id == item.id), None)
        if line is None:
            cart.lines.append(CartLineRecord(item=item, quantity=1))
        else:
            line.quantity += 1
        Store.cart_price(cart)
        session.commit()

    @staticmethod
    def update_item(session: Session, item: ItemRecord, data: Item) -> None:
        carts = session.scalars(
            select(CartRecord)
            .join(CartLineRecord)
            .where(CartLineRecord.item_id == item.id)
            .options(selectinload(CartRecord.lines).selectinload(CartLineRecord.item))
        ).unique()
        for cart in carts:
            Store.cart_price(cart, data)
        item.name = data.name
        item.price = data.price
        item.deleted = data.deleted
        session.commit()
