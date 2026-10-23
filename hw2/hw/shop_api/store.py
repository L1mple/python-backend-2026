from sqlalchemy import select
from sqlalchemy.orm import Session

from shop_api.database import SessionLocal
from shop_api.models import (
    CartEntity,
    CartItemEntity,
    CartLine,
    CartView,
    ItemEntity,
)


class ShopStore:
    def create_cart(self) -> int:
        with SessionLocal.begin() as session:
            cart = CartEntity()
            session.add(cart)
            session.flush()
            return cart.id

    def get_cart(self, cart_id: int) -> CartView | None:
        with SessionLocal() as session:
            cart = session.get(CartEntity, cart_id)
            return self._view(session, cart) if cart is not None else None

    def list_carts(
        self,
        *,
        offset: int,
        limit: int,
        min_price: float | None,
        max_price: float | None,
        min_quantity: int | None,
        max_quantity: int | None,
    ) -> list[CartView]:
        with SessionLocal() as session:
            carts = session.scalars(select(CartEntity).order_by(CartEntity.id)).all()
            views = [self._view(session, cart) for cart in carts]
            filtered = [
                view
                for view in views
                if _price_matches(view.price, min_price, max_price)
                and _quantity_matches(
                    _total_quantity(view),
                    min_quantity,
                    max_quantity,
                )
            ]
            return filtered[offset : offset + limit]

    def add_to_cart(self, cart_id: int, item_id: int) -> CartView | None:
        with SessionLocal.begin() as session:
            cart = session.scalar(
                select(CartEntity)
                .where(CartEntity.id == cart_id)
                .with_for_update()
            )
            item = session.get(ItemEntity, item_id)
            if cart is None or item is None or item.deleted:
                return None

            line = session.get(CartItemEntity, (cart_id, item_id))
            if line is None:
                session.add(
                    CartItemEntity(cart_id=cart_id, item_id=item_id, quantity=1)
                )
            else:
                line.quantity += 1
            session.flush()
            return self._view(session, cart)

    def create_item(self, name: str, price: float) -> ItemEntity:
        with SessionLocal.begin() as session:
            item = ItemEntity(name=name, price=price)
            session.add(item)
            session.flush()
            return item

    def get_item(self, item_id: int, *, include_deleted: bool = False) -> ItemEntity | None:
        with SessionLocal() as session:
            item = session.get(ItemEntity, item_id)
            if item is None or (item.deleted and not include_deleted):
                return None
            return item

    def list_items(
        self,
        *,
        offset: int,
        limit: int,
        min_price: float | None,
        max_price: float | None,
        show_deleted: bool,
    ) -> list[ItemEntity]:
        statement = select(ItemEntity).order_by(ItemEntity.id)
        if not show_deleted:
            statement = statement.where(ItemEntity.deleted.is_(False))
        if min_price is not None:
            statement = statement.where(ItemEntity.price >= min_price)
        if max_price is not None:
            statement = statement.where(ItemEntity.price <= max_price)
        statement = statement.offset(offset).limit(limit)

        with SessionLocal() as session:
            return list(session.scalars(statement))

    def replace_item(self, item_id: int, name: str, price: float) -> ItemEntity | None:
        with SessionLocal.begin() as session:
            item = session.get(ItemEntity, item_id)
            if item is None:
                return None
            item.name = name
            item.price = price
            session.flush()
            return item

    def patch_item(
        self,
        item_id: int,
        *,
        name: str | None,
        price: float | None,
    ) -> ItemEntity | None:
        with SessionLocal.begin() as session:
            item = session.get(ItemEntity, item_id)
            if item is None or item.deleted:
                return item
            if name is not None:
                item.name = name
            if price is not None:
                item.price = price
            session.flush()
            return item

    def delete_item(self, item_id: int) -> ItemEntity | None:
        with SessionLocal.begin() as session:
            item = session.get(ItemEntity, item_id)
            if item is None:
                return None
            item.deleted = True
            session.flush()
            return item

    @staticmethod
    def _view(session: Session, cart: CartEntity) -> CartView:
        rows = session.execute(
            select(CartItemEntity, ItemEntity)
            .join(ItemEntity, ItemEntity.id == CartItemEntity.item_id)
            .where(CartItemEntity.cart_id == cart.id)
            .order_by(ItemEntity.id)
        ).all()

        lines: list[CartLine] = []
        price = 0.0
        for cart_item, item in rows:
            lines.append(
                CartLine(
                    id=item.id,
                    name=item.name,
                    quantity=cart_item.quantity,
                    available=not item.deleted,
                )
            )
            price += item.price * cart_item.quantity

        return CartView(id=cart.id, items=lines, price=price)


def _price_matches(price: float, min_price: float | None, max_price: float | None) -> bool:
    if min_price is not None and price < min_price:
        return False

    if max_price is not None and price > max_price:
        return False

    return True


def _total_quantity(cart: CartView) -> int:
    return sum(line.quantity for line in cart.items)


def _quantity_matches(
    quantity: int,
    min_quantity: int | None,
    max_quantity: int | None,
) -> bool:
    if min_quantity is not None and quantity < min_quantity:
        return False

    if max_quantity is not None and quantity > max_quantity:
        return False

    return True


store = ShopStore()
