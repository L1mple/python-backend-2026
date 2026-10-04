from typing import Iterable

from .models import CartEntity, CartItemEntity, ItemEntity, ItemInfo, PatchItemInfo


_items: dict[int, ItemInfo] = {}
_carts: dict[int, dict[int, int]] = {}


def id_generator() -> Iterable[int]:
    value = 1
    while True:
        yield value
        value += 1


_item_ids = id_generator()
_cart_ids = id_generator()


def make_cart_entity(cart_id: int) -> CartEntity:
    result = []
    for item_id, quantity in _carts[cart_id].items():
        item = _items[item_id]
        result.append(
            CartItemEntity(
                id=item_id,
                name=item.name,
                price=item.price,
                quantity=quantity,
                available=not item.deleted,
            )
        )
    return CartEntity(id=cart_id, items=result)


def add_item(info: ItemInfo) -> ItemEntity:
    item_id = next(_item_ids)
    _items[item_id] = info
    return ItemEntity(item_id, info)


def get_item(item_id: int) -> ItemEntity | None:
    if item_id not in _items:
        return None
    return ItemEntity(item_id, _items[item_id])


def get_items(
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    show_deleted: bool,
) -> list[ItemEntity]:
    result = []
    for item_id, info in _items.items():
        if info.deleted and not show_deleted:
            continue
        if min_price is not None and info.price < min_price:
            continue
        if max_price is not None and info.price > max_price:
            continue
        result.append(ItemEntity(item_id, info))
    return result[offset : offset + limit]


def update_item(item_id: int, info: ItemInfo) -> ItemEntity | None:
    old_item = _items.get(item_id)
    if old_item is None or old_item.deleted:
        return None
    _items[item_id] = info
    return ItemEntity(item_id, info)


def patch_item(item_id: int, patch: PatchItemInfo) -> ItemEntity | None:
    item = _items.get(item_id)
    if item is None or item.deleted:
        return None
    if patch.name is not None:
        item.name = patch.name
    if patch.price is not None:
        item.price = patch.price
    return ItemEntity(item_id, item)


def delete_item(item_id: int) -> ItemEntity | None:
    item = _items.get(item_id)
    if item is None:
        return None
    item.deleted = True
    return ItemEntity(item_id, item)


def add_cart() -> CartEntity:
    cart_id = next(_cart_ids)
    _carts[cart_id] = {}
    return make_cart_entity(cart_id)


def get_cart(cart_id: int) -> CartEntity | None:
    if cart_id not in _carts:
        return None
    return make_cart_entity(cart_id)


def get_carts(
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    min_quantity: int | None,
    max_quantity: int | None,
) -> list[CartEntity]:
    result = []
    for cart_id, data in _carts.items():
        cart = make_cart_entity(cart_id)
        price = sum(item.price * item.quantity for item in cart.items)
        quantity = sum(data.values())
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
    if cart_id not in _carts or item_id not in _items or _items[item_id].deleted:
        return None
    cart = _carts[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1
    return make_cart_entity(cart_id)
