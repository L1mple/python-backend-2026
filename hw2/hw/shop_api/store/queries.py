from typing import Iterable

from shop_api.store.database import Cart, CartItem, Item, SessionLocal
from shop_api.store.models import CartEntity, ItemEntity, ItemInfo, PatchItemInfo


def _item_entity(item: Item) -> ItemEntity:
    return ItemEntity(
        id=item.id,
        info=ItemInfo(name=item.name, price=item.price, deleted=item.deleted),
    )


def _cart_items(session, cart_id: int) -> dict[int, int]:
    rows = session.query(CartItem).filter_by(cart_id=cart_id).all()
    return {row.item_id: row.quantity for row in rows}


def add_item(info: ItemInfo) -> ItemEntity:
    session = SessionLocal()
    item = Item(name=info.name, price=info.price, deleted=False)
    session.add(item)
    session.commit()
    session.refresh(item)
    result = _item_entity(item)
    session.close()
    return result


def get_item(item_id: int) -> ItemEntity | None:
    session = SessionLocal()
    item = session.get(Item, item_id)
    if item is None:
        session.close()
        return None
    result = _item_entity(item)
    session.close()
    return result


def get_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> list[ItemEntity]:
    session = SessionLocal()
    query = session.query(Item)
    if not show_deleted:
        query = query.filter(Item.deleted.is_(False))
    if min_price is not None:
        query = query.filter(Item.price >= min_price)
    if max_price is not None:
        query = query.filter(Item.price <= max_price)

    items = query.order_by(Item.id).offset(offset).limit(limit).all()
    result = [_item_entity(item) for item in items]
    session.close()
    return result


def update_item(item_id: int, name: str, price: float) -> ItemEntity | None:
    session = SessionLocal()
    item = session.get(Item, item_id)
    if item is None:
        session.close()
        return None
    item.name = name
    item.price = price
    session.commit()
    session.refresh(item)
    result = _item_entity(item)
    session.close()
    return result


def patch_item(item_id: int, patch: PatchItemInfo) -> ItemEntity | None:
    session = SessionLocal()
    item = session.get(Item, item_id)
    if item is None or item.deleted:
        session.close()
        return None
    if patch.name is not None:
        item.name = patch.name
    if patch.price is not None:
        item.price = patch.price
    session.commit()
    session.refresh(item)
    result = _item_entity(item)
    session.close()
    return result


def delete_item(item_id: int) -> None:
    session = SessionLocal()
    item = session.get(Item, item_id)
    if item is not None:
        item.deleted = True
        session.commit()
    session.close()


def add_cart() -> CartEntity:
    session = SessionLocal()
    cart = Cart()
    session.add(cart)
    session.commit()
    session.refresh(cart)
    result = CartEntity(cart.id, {})
    session.close()
    return result


def get_cart(cart_id: int) -> CartEntity | None:
    session = SessionLocal()
    cart = session.get(Cart, cart_id)
    if cart is None:
        session.close()
        return None
    result = CartEntity(cart.id, _cart_items(session, cart_id))
    session.close()
    return result


def get_carts() -> Iterable[CartEntity]:
    session = SessionLocal()
    carts = session.query(Cart).order_by(Cart.id).all()
    result = [CartEntity(cart.id, _cart_items(session, cart.id)) for cart in carts]
    session.close()
    return result


def add_to_cart(cart_id: int, item_id: int) -> CartEntity | None:
    session = SessionLocal()
    cart = session.get(Cart, cart_id)
    item = session.get(Item, item_id)
    if cart is None or item is None:
        session.close()
        return None

    cart_item = session.get(CartItem, {'cart_id': cart_id, 'item_id': item_id})
    if cart_item is None:
        session.add(CartItem(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        cart_item.quantity += 1

    session.commit()
    result = CartEntity(cart_id, _cart_items(session, cart_id))
    session.close()
    return result
