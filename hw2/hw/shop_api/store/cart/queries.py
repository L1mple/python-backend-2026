from typing import Iterable

from shop_api.store.cart.models import (
    CartItem,
    CartInfo,
    CartEntity
)
from shop_api.store.item import ItemEntity

_data = dict[int, CartInfo]()


def int_id_generator() -> Iterable[int]:
    i = 0
    while True:
        yield i
        i += 1


_id_generator = int_id_generator()


def add() -> int:
    _id = next(_id_generator)
    _data[_id] = CartInfo()

    return _id


def get_one(id: int) -> CartEntity | None:
    if id not in _data:
        return None

    return CartEntity(id=id, info=_data[id])


def get_many(offset: int = 0, 
             limit: int = 10, 
             min_price: float | None = None,
             max_price: float | None = None,
             min_quantity: int | None = None,
             max_quantity: int | None = None) -> Iterable[CartEntity]:
    curr = 0
    for id, info in _data.items():
        quantity = sum(cartItem.quantity for cartItem in info.items)
        if all((offset <= curr < offset + limit,
               min_price is None or info.price >= min_price,
               max_price is None or info.price <= max_price,
               min_quantity is None or quantity >= min_quantity,
               max_quantity is None or quantity <= max_quantity)):
            yield CartEntity(id, info)

        curr += 1


def add_item(id: int, new_item: ItemEntity) -> CartEntity | None:
    if id not in _data:
        return None
    _data[id].price += new_item.info.price
    for item in _data[id].items:
        if item.info.id == new_item.id:
            item.quantity += 1
            return CartEntity(id, _data[id])
    _data[id].items.append(CartItem(new_item, 1))
    return CartEntity(id, _data[id])
