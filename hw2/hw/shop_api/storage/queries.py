from typing import Iterable

from .models import Cart, CartItem, Item


_items: dict[int, Item] = {}
_carts: dict[int, Cart] = {}


def int_item_id_generator() -> Iterable[int]:
    i = 0
    while True:
        yield i
        i += 1


def int_cart_id_generator() -> Iterable[int]:
    i = 0
    while True:
        yield i
        i += 1


_item_id_generator = int_item_id_generator()
_cart_id_generator = int_cart_id_generator()


def add_item(name: str, price: float) -> Item:
    item_id = next(_item_id_generator)
    item = Item(id=item_id, name=name, price=price)
    _items[item_id] = item
    return item


def get_item(item_id: int, show_deleted: bool = False) -> Item | None:
    item = _items.get(item_id)
    if item is None or item.deleted and not show_deleted:
        return None
    return item


def get_items(offset: int = 0, limit: int = 10, min_price: float | None = None, max_price: float | None = None, show_deleted: bool = False) -> list[Item]:
    result = []
    for item in _items.values():
        if item.deleted and not show_deleted:
            continue
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue
        result.append(item)
    return result[offset : offset + limit]


def update_item(item_id: int, name: str, price: float) -> Item | None:
    item = get_item(item_id)
    if item is None:
        return None
    item.name = name
    item.price = price
    return item


def patch_item(item_id: int, name: str | None = None, price: float | None = None) -> Item | None:
    item = get_item(item_id)
    if item is None:
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


def _refresh_cart(cart: Cart) -> Cart:
    cart.price = 0.
    for cart_item in cart.items:
        item = _items.get(cart_item.id)
        cart_item.available = item is not None and not item.deleted
        if item is not None:
            cart_item.name = item.name
        if cart_item.available:
            cart.price += item.price * cart_item.quantity
    return cart


def add_cart() -> Cart:
    cart_id = next(_cart_id_generator)
    cart = Cart(id=cart_id)
    _carts[cart_id] = cart
    return cart


def get_cart(cart_id: int) -> Cart | None:
    cart = _carts.get(cart_id)
    if cart is None:
        return None
    return _refresh_cart(cart)


def get_carts(offset: int = 0, limit: int = 10, min_price: float | None = None, max_price: float | None = None, min_quantity: int | None = None, max_quantity: int | None = None) -> list[Cart]:
    result = []
    for cart in _carts.values():
        _refresh_cart(cart)
        quantity = sum(item.quantity for item in cart.items)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(cart)
    return result[offset : offset + limit]


def add_item_to_cart(cart_id: int, item_id: int) -> Cart | None:
    cart = _carts.get(cart_id)
    item = get_item(item_id)
    if cart is None or item is None:
        return None
    for cart_item in cart.items:
        if cart_item.id == item_id:
            cart_item.quantity += 1
            return _refresh_cart(cart)
    cart.items.append(CartItem(id=item.id, name=item.name, quantity=1, available=True))
    return _refresh_cart(cart)
