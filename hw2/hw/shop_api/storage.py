from dataclasses import dataclass, field
from itertools import count


@dataclass(slots=True)
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class Cart:
    id: int
    # id товара -> количество в корзине
    items: dict[int, int] = field(default_factory=dict)


# Данные хранятся в памяти процесса и пропадают при перезапуске
_items: dict[int, Item] = {}
_carts: dict[int, Cart] = {}

_item_ids = count()
_cart_ids = count()


def add_item(name: str, price: float) -> Item:
    item = Item(id=next(_item_ids), name=name, price=price)
    _items[item.id] = item
    return item


def get_item(item_id: int) -> Item | None:
    return _items.get(item_id)


def all_items() -> list[Item]:
    return list(_items.values())


def add_cart() -> Cart:
    cart = Cart(id=next(_cart_ids))
    _carts[cart.id] = cart
    return cart


def get_cart(cart_id: int) -> Cart | None:
    return _carts.get(cart_id)


def all_carts() -> list[Cart]:
    return list(_carts.values())


def add_to_cart(cart: Cart, item: Item) -> None:
    cart.items[item.id] = cart.items.get(item.id, 0) + 1
