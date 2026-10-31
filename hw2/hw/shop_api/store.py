from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from shop_api.db import CartItemModel, CartModel, ItemModel, SessionLocal


@dataclass(slots=True)
class ItemInfo:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class CartItemInfo:
    id: int
    name: str
    quantity: int
    available: bool


@dataclass(slots=True)
class CartInfo:
    id: int
    items: list[CartItemInfo]
    price: float


def _item_info(model: ItemModel) -> ItemInfo:
    return ItemInfo(
        id=model.id,
        name=model.name,
        price=model.price,
        deleted=model.deleted,
    )


def add_item(name: str, price: float) -> ItemInfo:
    with SessionLocal.begin() as session:
        model = ItemModel(name=name, price=price, deleted=False)
        session.add(model)
        session.flush()
        return _item_info(model)


def get_item(item_id: int) -> ItemInfo | None:
    with SessionLocal() as session:
        model = session.get(ItemModel, item_id)
        return _item_info(model) if model else None


def list_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> list[ItemInfo]:
    stmt = select(ItemModel)
    if not show_deleted:
        stmt = stmt.where(ItemModel.deleted.is_(False))
    if min_price is not None:
        stmt = stmt.where(ItemModel.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(ItemModel.price <= max_price)
    stmt = stmt.order_by(ItemModel.id).offset(offset).limit(limit)

    with SessionLocal() as session:
        return [_item_info(model) for model in session.scalars(stmt)]


def replace_item(item_id: int, name: str, price: float) -> ItemInfo | None:
    with SessionLocal.begin() as session:
        model = session.get(ItemModel, item_id)
        if model is None:
            return None
        model.name = name
        model.price = price
        return _item_info(model)


def patch_item(item_id: int, name: str | None, price: float | None) -> ItemInfo | None:
    with SessionLocal.begin() as session:
        model = session.get(ItemModel, item_id)
        if model is None:
            return None
        if name is not None:
            model.name = name
        if price is not None:
            model.price = price
        return _item_info(model)


def delete_item(item_id: int) -> ItemInfo | None:
    with SessionLocal.begin() as session:
        model = session.get(ItemModel, item_id)
        if model is None:
            return None
        model.deleted = True
        return _item_info(model)


def add_cart() -> CartInfo:
    with SessionLocal.begin() as session:
        model = CartModel()
        session.add(model)
        session.flush()
        return CartInfo(id=model.id, items=[], price=0.0)


def _load_cart(session: Session, cart_id: int) -> CartInfo | None:
    if session.get(CartModel, cart_id) is None:
        return None

    rows = session.execute(
        select(ItemModel, CartItemModel.quantity)
        .join(CartItemModel, CartItemModel.item_id == ItemModel.id)
        .where(CartItemModel.cart_id == cart_id)
        .order_by(ItemModel.id)
    ).all()

    items = [
        CartItemInfo(
            id=item.id,
            name=item.name,
            quantity=quantity,
            available=not item.deleted,
        )
        for item, quantity in rows
    ]
    price = sum((item.price * quantity for item, quantity in rows), 0.0)
    return CartInfo(id=cart_id, items=items, price=price)


def get_cart(cart_id: int) -> CartInfo | None:
    with SessionLocal() as session:
        return _load_cart(session, cart_id)


def list_carts(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> list[CartInfo]:
    price = func.coalesce(func.sum(ItemModel.price * CartItemModel.quantity), 0.0)
    quantity = func.coalesce(func.sum(CartItemModel.quantity), 0)

    stmt = (
        select(CartModel.id)
        .outerjoin(CartItemModel, CartItemModel.cart_id == CartModel.id)
        .outerjoin(ItemModel, ItemModel.id == CartItemModel.item_id)
        .group_by(CartModel.id)
    )
    if min_price is not None:
        stmt = stmt.having(price >= min_price)
    if max_price is not None:
        stmt = stmt.having(price <= max_price)
    if min_quantity is not None:
        stmt = stmt.having(quantity >= min_quantity)
    if max_quantity is not None:
        stmt = stmt.having(quantity <= max_quantity)
    stmt = stmt.order_by(CartModel.id).offset(offset).limit(limit)

    with SessionLocal() as session:
        cart_ids = session.scalars(stmt).all()
        carts = [_load_cart(session, cart_id) for cart_id in cart_ids]
        return [cart for cart in carts if cart is not None]


def add_item_to_cart(cart_id: int, item_id: int) -> CartInfo | None:
    with SessionLocal.begin() as session:
        if session.get(CartModel, cart_id) is None:
            return None
        if session.get(ItemModel, item_id) is None:
            return None

        stmt = pg_insert(CartItemModel).values(
            cart_id=cart_id,
            item_id=item_id,
            quantity=1,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["cart_id", "item_id"],
            set_={"quantity": CartItemModel.quantity + 1},
        )
        session.execute(stmt)
        return _load_cart(session, cart_id)