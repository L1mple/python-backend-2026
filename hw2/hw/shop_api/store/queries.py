from typing import Iterable

from shop_api.store.models import CartEntity, ItemEntity, ItemInfo, PatchItemInfo

_items = dict[int, ItemInfo]()
_carts = dict[int, dict[int, int]]()
_item_id = 0
_cart_id = 0


def add_item(info: ItemInfo) -> ItemEntity:
    global _item_id
    _item_id += 1
    _items[_item_id] = info
    return ItemEntity(_item_id, info)


def get_item(item_id: int) -> ItemEntity | None:
    if item_id not in _items:
        return None
    return ItemEntity(item_id, _items[item_id])


def get_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> list[ItemEntity]:
    result = []
    for item_id, info in _items.items():
        if not show_deleted and info.deleted:
            continue
        if min_price is not None and info.price < min_price:
            continue
        if max_price is not None and info.price > max_price:
            continue
        result.append(ItemEntity(item_id, info))
    return result[offset:offset + limit]


def update_item(item_id: int, name: str, price: float) -> ItemEntity | None:
    if item_id not in _items:
        return None
    _items[item_id].name = name
    _items[item_id].price = price
    return ItemEntity(item_id, _items[item_id])


def patch_item(item_id: int, patch: PatchItemInfo) -> ItemEntity | None:
    if item_id not in _items or _items[item_id].deleted:
        return None
    if patch.name is not None:
        _items[item_id].name = patch.name
    if patch.price is not None:
        _items[item_id].price = patch.price
    return ItemEntity(item_id, _items[item_id])


def delete_item(item_id: int) -> None:
    if item_id in _items:
        _items[item_id].deleted = True


def add_cart() -> CartEntity:
    global _cart_id
    _cart_id += 1
    _carts[_cart_id] = {}
    return CartEntity(_cart_id, _carts[_cart_id])


def get_cart(cart_id: int) -> CartEntity | None:
    if cart_id not in _carts:
        return None
    return CartEntity(cart_id, _carts[cart_id])


def get_carts() -> Iterable[CartEntity]:
    for cart_id, items in _carts.items():
        yield CartEntity(cart_id, items)


def add_to_cart(cart_id: int, item_id: int) -> CartEntity | None:
    if cart_id not in _carts or item_id not in _items:
        return None
    if item_id in _carts[cart_id]:
        _carts[cart_id][item_id] += 1
    else:
        _carts[cart_id][item_id] = 1
    return CartEntity(cart_id, _carts[cart_id])
