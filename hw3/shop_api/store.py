from dataclasses import dataclass, field
from itertools import count


@dataclass(slots=True)
class ItemRecord:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class CartRecord:
    id: int
    items: dict[int, int] = field(default_factory=dict)


_items: dict[int, ItemRecord] = {}
_carts: dict[int, CartRecord] = {}
_item_ids = count(1)
_cart_ids = count(1)


def add_item(name: str, price: float) -> ItemRecord:
    item = ItemRecord(id=next(_item_ids), name=name, price=price)
    _items[item.id] = item
    return item


def get_item(item_id: int) -> ItemRecord | None:
    """Товар по id, включая удалённые (решение «показывать или нет» — в роутере)."""
    return _items.get(item_id)


def list_items() -> list[ItemRecord]:
    return list(_items.values())




def add_cart() -> CartRecord:
    cart = CartRecord(id=next(_cart_ids))
    _carts[cart.id] = cart
    return cart


def get_cart(cart_id: int) -> CartRecord | None:
    return _carts.get(cart_id)


def list_carts() -> list[CartRecord]:
    return list(_carts.values())
