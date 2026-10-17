from typing import Annotated

from fastapi import Depends
from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .database import CartItemRow, CartRow, ItemRow, get_session
from .models import (
    Cart,
    CartFilters,
    CartItem,
    Item,
    ItemData,
    ItemFilters,
    ItemPatch,
    ItemReplacement,
)


class Store:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def to_item(row: ItemRow) -> Item:
        return Item(id=row.id, name=row.name, price=row.price, deleted=row.deleted)

    def create_item(self, data: ItemData) -> Item:
        row = ItemRow(**data.model_dump())
        self.session.add(row)
        self.session.flush()
        return self.to_item(row)

    def get_item(self, item_id: int, lock: bool = False) -> Item | None:
        query = select(ItemRow).where(ItemRow.id == item_id)
        if lock:
            query = query.with_for_update()
        row = self.session.scalar(query)
        return self.to_item(row) if row is not None else None

    def list_items(self, filters: ItemFilters) -> list[Item]:
        query = select(ItemRow)
        if not filters.show_deleted:
            query = query.where(ItemRow.deleted.is_(False))
        if filters.min_price is not None:
            query = query.where(ItemRow.price >= filters.min_price)
        if filters.max_price is not None:
            query = query.where(ItemRow.price <= filters.max_price)
        query = query.order_by(ItemRow.id).offset(filters.offset).limit(filters.limit)
        return [self.to_item(row) for row in self.session.scalars(query)]

    def replace_item(self, item_id: int, data: ItemReplacement) -> Item:
        row = self.session.scalar(
            update(ItemRow)
            .where(ItemRow.id == item_id)
            .values(**data.model_dump())
            .returning(ItemRow)
        )
        return self.to_item(row)

    def patch_item(self, item_id: int, data: ItemPatch) -> Item:
        values = data.model_dump(exclude_unset=True)
        if not values:
            return self.get_item(item_id)
        row = self.session.scalar(
            update(ItemRow)
            .where(ItemRow.id == item_id)
            .values(**values)
            .returning(ItemRow)
        )
        return self.to_item(row)

    def delete_item(self, item_id: int) -> None:
        self.session.execute(
            update(ItemRow).where(ItemRow.id == item_id).values(deleted=True)
        )

    def create_cart(self) -> int:
        row = CartRow()
        self.session.add(row)
        self.session.flush()
        return row.id

    def read_carts(self, cart_ids) -> list[Cart]:
        query = (
            select(CartRow.id, ItemRow, CartItemRow.quantity)
            .outerjoin(CartItemRow, CartItemRow.cart_id == CartRow.id)
            .outerjoin(ItemRow, ItemRow.id == CartItemRow.item_id)
            .where(CartRow.id.in_(cart_ids))
            .order_by(CartRow.id, ItemRow.id)
        )
        carts: dict[int, Cart] = {}
        for cart_id, item, quantity in self.session.execute(query):
            cart = carts.setdefault(cart_id, Cart(id=cart_id, items=[], price=0.0))
            if item is not None:
                cart.items.append(
                    CartItem(
                        id=item.id,
                        name=item.name,
                        quantity=quantity,
                        available=not item.deleted,
                    )
                )
                if not item.deleted:
                    cart.price += item.price * quantity
        return list(carts.values())

    def get_cart(self, cart_id: int, lock: bool = False) -> Cart | None:
        if lock:
            self.session.scalar(
                select(CartRow.id).where(CartRow.id == cart_id).with_for_update()
            )
        carts = self.read_carts([cart_id])
        return carts[0] if carts else None

    def list_carts(self, filters: CartFilters) -> list[Cart]:
        price = func.coalesce(
            func.sum(
                case(
                    (ItemRow.deleted.is_(False), ItemRow.price * CartItemRow.quantity),
                    else_=0.0,
                )
            ),
            0.0,
        )
        quantity = func.coalesce(func.sum(CartItemRow.quantity), 0)
        query = (
            select(CartRow.id)
            .outerjoin(CartItemRow, CartItemRow.cart_id == CartRow.id)
            .outerjoin(ItemRow, ItemRow.id == CartItemRow.item_id)
            .group_by(CartRow.id)
        )
        for field, minimum, maximum in (
            (price, filters.min_price, filters.max_price),
            (quantity, filters.min_quantity, filters.max_quantity),
        ):
            if minimum is not None:
                query = query.having(field >= minimum)
            if maximum is not None:
                query = query.having(field <= maximum)
        query = query.order_by(CartRow.id).offset(filters.offset).limit(filters.limit)
        return self.read_carts(query)

    def add_item(self, cart_id: int, item_id: int) -> None:
        self.session.execute(
            insert(CartItemRow)
            .values(cart_id=cart_id, item_id=item_id, quantity=1)
            .on_conflict_do_update(
                index_elements=[CartItemRow.cart_id, CartItemRow.item_id],
                set_={"quantity": CartItemRow.quantity + 1},
            )
        )


def get_store(session: Annotated[Session, Depends(get_session)]) -> Store:
    return Store(session)


StoreDependency = Annotated[Store, Depends(get_store)]
