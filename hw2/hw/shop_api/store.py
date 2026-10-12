"""Shop queries. Cart views reflect current item names, prices and deletion."""

from math import fsum

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import CartLineRecord, CartRecord, ItemRecord
from .models import Cart, CartItem, Item, ItemData, ItemPatch


class ShopStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_item(self, item_id: int, *, lock: bool = False) -> ItemRecord | None:
        query = select(ItemRecord).where(ItemRecord.id == item_id)
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    def list_items(
        self,
        offset: int,
        limit: int,
        min_price: float | None,
        max_price: float | None,
        show_deleted: bool,
    ) -> list[Item]:
        query = select(ItemRecord).order_by(ItemRecord.id)
        if not show_deleted:
            query = query.where(ItemRecord.deleted.is_(False))
        if min_price is not None:
            query = query.where(ItemRecord.price >= min_price)
        if max_price is not None:
            query = query.where(ItemRecord.price <= max_price)
        return [
            Item.model_validate(row, from_attributes=True)
            for row in self.session.scalars(query.offset(offset).limit(limit))
        ]

    def create_item(self, data: ItemData) -> Item:
        row = ItemRecord(**data.model_dump())
        self.session.add(row)
        self.session.flush()
        return Item.model_validate(row, from_attributes=True)

    def replace_item(self, row: ItemRecord, data: ItemData) -> Item:
        row.name, row.price, row.deleted = data.name, data.price, data.deleted
        return Item.model_validate(row, from_attributes=True)

    def patch_item(self, row: ItemRecord, data: ItemPatch) -> Item:
        if data.name is not None:
            row.name = data.name
        if data.price is not None:
            row.price = data.price
        return Item.model_validate(row, from_attributes=True)

    def create_cart(self) -> int:
        row = CartRecord()
        self.session.add(row)
        self.session.flush()
        return row.id

    def get_cart_record(self, cart_id: int, *, lock: bool = False) -> CartRecord | None:
        query = select(CartRecord).where(CartRecord.id == cart_id)
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    def cart_ids(self) -> list[int]:
        return list(self.session.scalars(select(CartRecord.id).order_by(CartRecord.id)))

    def get_cart(self, cart_id: int) -> Cart:
        rows = self.session.execute(
            select(ItemRecord, CartLineRecord.quantity)
            .join(CartLineRecord, CartLineRecord.item_id == ItemRecord.id)
            .where(CartLineRecord.cart_id == cart_id)
            .order_by(CartLineRecord.id)
        ).all()
        return Cart(
            id=cart_id,
            items=[
                CartItem(id=row.id, name=row.name, quantity=quantity, available=not row.deleted)
                for row, quantity in rows
            ],
            price=fsum(row.price * quantity for row, quantity in rows if not row.deleted),
        )

    def add_to_cart(self, cart_id: int, item_id: int) -> Cart:
        # The caller locks the cart row, serializing concurrent additions to this cart.
        line = self.session.scalar(
            select(CartLineRecord).where(
                CartLineRecord.cart_id == cart_id, CartLineRecord.item_id == item_id
            )
        )
        if line is None:
            self.session.add(CartLineRecord(cart_id=cart_id, item_id=item_id, quantity=1))
        else:
            line.quantity += 1
        self.session.flush()
        return self.get_cart(cart_id)
