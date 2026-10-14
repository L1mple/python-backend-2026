from __future__ import annotations

from itertools import count
from typing import Iterable

from store.cart.models import CartEntity
from store.item import queries as item_queries

_carts: dict[int, CartEntity] = {}
_id_generator = count(start=1)


def add() -> CartEntity:
    cart_id = next(_id_generator)
    entity = CartEntity(id=cart_id, items={})
    _carts[cart_id] = entity
    return entity


def get(cart_id: int) -> CartEntity | None:
    return _carts.get(cart_id)


def add_item(cart_id: int, item_id: int) -> CartEntity | None:
    cart = _carts.get(cart_id)
    if cart is None:
        return None
    cart.items[item_id] = cart.items.get(item_id, 0) + 1
    return cart


def total_price(cart: CartEntity) -> float:
    price = 0.0
    for item_id, quantity in cart.items.items():
        item = item_queries.get(item_id)
        if item is not None:
            price += item.price * quantity
    return price


def total_quantity(cart: CartEntity) -> int:
    return sum(cart.items.values())


def get_many(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> Iterable[CartEntity]:
    result = []
    for cart in _carts.values():
        price = total_price(cart)
        quantity = total_quantity(cart)
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
