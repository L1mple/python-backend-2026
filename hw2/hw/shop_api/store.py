from typing import Iterable

from .models import Cart, Item


_items: dict[int, Item] = {}
_carts: dict[int, Cart] = {}


def int_id_generator() -> Iterable[int]:
    i = 0

    while True:
        yield i
        i += 1


_item_id_generator = int_id_generator()
_cart_id_generator = int_id_generator()


def add_item(name: str, price: float) -> Item:
    item_id = next(_item_id_generator)

    item = Item(
        id=item_id,
        name=name,
        price=price,
    )

    _items[item_id] = item

    return item


def get_item(item_id: int) -> Item | None:
    return _items.get(item_id)


def get_all_items() -> Iterable[Item]:
    return _items.values()


def update_item(
    item_id: int,
    name: str,
    price: float,
) -> Item | None:
    item = _items.get(item_id)

    if item is None or item.deleted:
        return None

    item.name = name
    item.price = price

    return item


def patch_item(
    item_id: int,
    name: str | None = None,
    price: float | None = None,
) -> Item | None:
    item = _items.get(item_id)

    if item is None or item.deleted:
        return None

    if name is not None:
        item.name = name

    if price is not None:
        item.price = price

    return item


def delete_item(item_id: int) -> None:
    item = _items.get(item_id)

    if item is not None:
        item.deleted = True


def add_cart() -> Cart:
    cart_id = next(_cart_id_generator)

    cart = Cart(id=cart_id)
    _carts[cart_id] = cart

    return cart


def get_cart(cart_id: int) -> Cart | None:
    return _carts.get(cart_id)


def get_all_carts() -> Iterable[Cart]:
    return _carts.values()


def add_item_to_cart(
    cart_id: int,
    item_id: int,
) -> bool:
    cart = _carts.get(cart_id)
    item = _items.get(item_id)

    if cart is None or item is None or item.deleted:
        return False

    if item_id in cart.items:
        cart.items[item_id] += 1
    else:
        cart.items[item_id] = 1

    return True