from typing import Iterable

from .models import CartEntity, CartInfo


_data: dict[int, CartInfo] = {}


def int_id_generator() -> Iterable[int]:
    i = 0

    while True:
        yield i
        i += 1


_id_generator = int_id_generator()


def add_cart() -> CartEntity:
    cart_id = next(_id_generator)

    info = CartInfo()

    _data[cart_id] = info

    return CartEntity(
        id=cart_id,
        info=info,
    )


def get_cart(cart_id: int) -> CartEntity | None:
    if cart_id not in _data:
        return None

    return CartEntity(
        id=cart_id,
        info=_data[cart_id],
    )


def get_all_carts() -> Iterable[CartEntity]:
    for cart_id, info in _data.items():
        yield CartEntity(
            id=cart_id,
            info=info,
        )


def add_item_to_cart(
    cart_id: int,
    item_id: int,
) -> bool:
    if cart_id not in _data:
        return False

    items = _data[cart_id].items

    if item_id in items:
        items[item_id] += 1
    else:
        items[item_id] = 1

    return True