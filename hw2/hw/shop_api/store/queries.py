from typing import Iterable
from itertools import count
from shop_api.store.models import ItemEntity, ItemInfo, PatchItemInfo

_items: dict[int, ItemInfo] = {}
_carts: dict[int, dict[int, int]] = {}

_item_ids = count(1)
_cart_ids = count(1)


def add_item(info: ItemInfo) -> ItemEntity:
    item_id = next(_item_ids)
    _items[item_id] = info
    return ItemEntity(id=item_id, info=info)


def get_item(item_id: int) -> ItemEntity | None:
    if item_id not in _items:
        return None
    return ItemEntity(id=item_id, info=_items[item_id])


def get_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> Iterable[ItemEntity]:
    result: list[ItemEntity] = []

    for item_id, info in _items.items():
        if not show_deleted and info.deleted:
            continue
        if min_price is not None and info.price < min_price:
            continue
        if max_price is not None and info.price > max_price:
            continue

        result.append(ItemEntity(id=item_id, info=info))

    return result[offset : offset + limit]


def update_item(item_id: int, info: ItemInfo) -> ItemEntity | None:
    if item_id not in _items:
        return None
    _items[item_id] = info
    return ItemEntity(id=item_id, info=info)


def patch_item(item_id: int, patch: PatchItemInfo) -> ItemEntity | None:
    if item_id not in _items:
        return None

    info = _items[item_id]

    if patch.name is not None:
        info.name = patch.name
    if patch.price is not None:
        info.price = patch.price

    return ItemEntity(id=item_id, info=info)


def delete_item(item_id: int) -> None:
    if item_id in _items:
        _items[item_id].deleted = True


def add_cart() -> int:
    cart_id = next(_cart_ids)
    _carts[cart_id] = {}
    return cart_id


def get_cart(cart_id: int) -> dict[int, int] | None:
    return _carts.get(cart_id)


def get_carts() -> Iterable[tuple[int, dict[int, int]]]:
    return list(_carts.items())


def add_item_to_cart(cart_id: int, item_id: int) -> bool:
    if cart_id not in _carts or item_id not in _items:
        return False

    cart = _carts[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1
    return True
