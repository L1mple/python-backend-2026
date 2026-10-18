from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shop_api import models


def _item_to_dict(item: models.Item) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }


# ==================== ITEM ====================


def create_item(session: Session, name: str, price: float) -> dict[str, Any]:
    item = models.Item(name=name, price=price)
    session.add(item)
    session.commit()
    session.refresh(item)
    return _item_to_dict(item)


def get_item(session: Session, item_id: int) -> dict[str, Any] | None:
    item = session.get(models.Item, item_id)
    if item is None:
        return None
    return _item_to_dict(item)


def list_items(
    session: Session,
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    show_deleted: bool,
) -> list[dict[str, Any]]:
    stmt = select(models.Item)
    if not show_deleted:
        stmt = stmt.where(models.Item.deleted.is_(False))
    if min_price is not None:
        stmt = stmt.where(models.Item.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(models.Item.price <= max_price)
    stmt = stmt.offset(offset).limit(limit)
    items = session.execute(stmt).scalars().all()
    return [_item_to_dict(i) for i in items]


def replace_item(
    session: Session, item_id: int, name: str, price: float
) -> dict[str, Any] | None:
    item = session.get(models.Item, item_id)
    if item is None or item.deleted:
        return None
    item.name = name
    item.price = price
    session.commit()
    session.refresh(item)
    return _item_to_dict(item)


def patch_item(
    session: Session,
    item_id: int,
    name: str | None,
    price: float | None,
) -> dict[str, Any] | None:
    item = session.get(models.Item, item_id)
    if item is None or item.deleted:
        return None
    if name is not None:
        item.name = name
    if price is not None:
        item.price = price
    session.commit()
    session.refresh(item)
    return _item_to_dict(item)


def mark_item_deleted(session: Session, item_id: int) -> bool:
    item = session.get(models.Item, item_id)
    if item is None:
        return False
    item.deleted = True
    session.commit()
    return True


# ==================== CART ====================


def create_cart(session: Session) -> int:
    cart = models.Cart()
    session.add(cart)
    session.commit()
    session.refresh(cart)
    return cart.id


def get_cart_contents(session: Session, cart_id: int) -> dict[int, int] | None:
    cart = session.get(models.Cart, cart_id)
    if cart is None:
        return None
    return {ci.item_id: ci.quantity for ci in cart.items}


def add_item_to_cart(session: Session, cart_id: int, item_id: int) -> None:
    cart = session.get(models.Cart, cart_id)
    existing = next((ci for ci in cart.items if ci.item_id == item_id), None)
    if existing is None:
        session.add(models.CartItem(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        existing.quantity += 1
    session.commit()


def cart_price(session: Session, cart_id: int) -> float:
    cart = session.get(models.Cart, cart_id)
    return sum(ci.item.price * ci.quantity for ci in cart.items)


def cart_quantity(session: Session, cart_id: int) -> int:
    cart = session.get(models.Cart, cart_id)
    return sum(ci.quantity for ci in cart.items)


def list_carts(
    session: Session,
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    min_quantity: int | None,
    max_quantity: int | None,
) -> list[int]:
    carts = session.execute(select(models.Cart)).scalars().all()
    filtered = []
    for cart in carts:
        price = sum(ci.item.price * ci.quantity for ci in cart.items)
        quantity = sum(ci.quantity for ci in cart.items)
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        filtered.append(cart.id)
    return filtered[offset : offset + limit]
