from sqlalchemy import select

from .database import SessionLocal
from .models import CartEntity, CartItemEntity, ItemEntity, ItemInfo, PatchItemInfo
from .orm import CartItemOrm, CartOrm, ItemOrm


def make_item_entity(item: ItemOrm) -> ItemEntity:
    return ItemEntity(
        item.id,
        ItemInfo(name=item.name, price=item.price, deleted=item.deleted),
    )


def make_cart_entity(cart: CartOrm) -> CartEntity:
    return CartEntity(
        id=cart.id,
        items=[
            CartItemEntity(
                id=cart_item.item_id,
                name=cart_item.item.name,
                price=cart_item.item.price,
                quantity=cart_item.quantity,
                available=not cart_item.item.deleted,
            )
            for cart_item in cart.items
        ],
    )


def add_item(info: ItemInfo) -> ItemEntity:
    with SessionLocal.begin() as session:
        item = ItemOrm(name=info.name, price=info.price, deleted=info.deleted)
        session.add(item)
        session.flush()
        return make_item_entity(item)


def get_item(item_id: int) -> ItemEntity | None:
    with SessionLocal() as session:
        item = session.get(ItemOrm, item_id)
        return make_item_entity(item) if item else None


def get_items(
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    show_deleted: bool,
) -> list[ItemEntity]:
    query = select(ItemOrm)
    if not show_deleted:
        query = query.where(ItemOrm.deleted.is_(False))
    if min_price is not None:
        query = query.where(ItemOrm.price >= min_price)
    if max_price is not None:
        query = query.where(ItemOrm.price <= max_price)
    query = query.order_by(ItemOrm.id).offset(offset).limit(limit)

    with SessionLocal() as session:
        return [make_item_entity(item) for item in session.scalars(query)]


def update_item(item_id: int, info: ItemInfo) -> ItemEntity | None:
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, item_id)
        if item is None or item.deleted:
            return None
        item.name = info.name
        item.price = info.price
        return make_item_entity(item)


def patch_item(item_id: int, patch: PatchItemInfo) -> ItemEntity | None:
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, item_id)
        if item is None or item.deleted:
            return None
        if patch.name is not None:
            item.name = patch.name
        if patch.price is not None:
            item.price = patch.price
        return make_item_entity(item)


def delete_item(item_id: int) -> ItemEntity | None:
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, item_id)
        if item is None:
            return None
        item.deleted = True
        return make_item_entity(item)


def add_cart() -> CartEntity:
    with SessionLocal.begin() as session:
        cart = CartOrm()
        session.add(cart)
        session.flush()
        return CartEntity(id=cart.id)


def get_cart(cart_id: int) -> CartEntity | None:
    with SessionLocal() as session:
        cart = session.get(CartOrm, cart_id)
        return make_cart_entity(cart) if cart else None


def get_carts(
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    min_quantity: int | None,
    max_quantity: int | None,
) -> list[CartEntity]:
    with SessionLocal() as session:
        carts = [make_cart_entity(cart) for cart in session.scalars(select(CartOrm).order_by(CartOrm.id))]

    result = []
    for cart in carts:
        price = sum(item.price * item.quantity for item in cart.items)
        quantity = sum(item.quantity for item in cart.items)
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(cart)
    return result[offset : offset + limit]


def add_item_to_cart(cart_id: int, item_id: int) -> CartEntity | None:
    with SessionLocal.begin() as session:
        cart = session.get(CartOrm, cart_id)
        item = session.get(ItemOrm, item_id)
        if cart is None or item is None or item.deleted:
            return None

        cart_item = next((ci for ci in cart.items if ci.item_id == item_id), None)
        if cart_item is None:
            cart.items.append(CartItemOrm(item_id=item_id, item=item, quantity=1))
        else:
            cart_item.quantity += 1
        session.flush()
        return make_cart_entity(cart)
