from itertools import count
from .models import Cart, Item


_item_ids_counter = count(1)
_cart_ids_counter = count(1)
_id_to_item: dict[int, Item] = {}
_id_to_cart: dict[int, Cart] = {}


def add_item(name: str, price: float) -> Item:
    item = Item(id=next(_item_ids_counter), name=name, price=price)
    _id_to_item[item.id] = item
    return item


def get_item(id: int) -> Item | None:
    return _id_to_item.get(id)


def get_items(
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    show_deleted: bool,
) -> list[Item]:
    result = [
        item
        for item in _id_to_item.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return result[offset : offset + limit]


def update_item(id: int, name: str, price: float) -> Item | None:
    item = _id_to_item.get(id)
    if item is None or item.deleted:
        return None
    item.name = name
    item.price = price
    return item


def patch_item(id: int, name: str | None, price: float | None) -> Item | None:
    item = _id_to_item.get(id)
    if item is None or item.deleted:
        return None
    if name is not None:
        item.name = name
    if price is not None:
        item.price = price
    return item


def delete_item(id: int) -> None:
    item = _id_to_item.get(id)
    if item is not None:
        item.deleted = True


def add_cart() -> Cart:
    cart = Cart(id=next(_cart_ids_counter))
    _id_to_cart[cart.id] = cart
    return cart


def get_cart(id: int) -> Cart | None:
    return _id_to_cart.get(id)


def get_carts(
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    min_quantity: int | None,
    max_quantity: int | None,
) -> list[Cart]:
    result = [
        cart
        for cart in _id_to_cart.values()
        if (min_price is None or cart_price(cart) >= min_price)
        and (max_price is None or cart_price(cart) <= max_price)
        and (min_quantity is None or cart_quantity(cart) >= min_quantity)
        and (max_quantity is None or cart_quantity(cart) <= max_quantity)
    ]
    return result[offset : offset + limit]


def add_item_to_cart(cart_id: int, item_id: int) -> Cart | None:
    cart = _id_to_cart.get(cart_id)
    item = _id_to_item.get(item_id)
    if cart is None or item is None or item.deleted:
        return None
    cart.item_id_to_count[item_id] = cart.item_id_to_count.get(item_id, 0) + 1
    return cart


def cart_price(cart: Cart) -> float:
    return sum(
        _id_to_item[item_id].price * quantity
        for item_id, quantity in cart.item_id_to_count.items()
        if not _id_to_item[item_id].deleted
    )


def cart_quantity(cart: Cart) -> int:
    return sum(cart.item_id_to_count.values())
