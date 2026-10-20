from decimal import Decimal
from typing import Iterable

from store.general import int_id_generator
from store.cart.models import Cart

_data = dict[int, Cart]()

_id_generator = int_id_generator()


def add() -> Cart:
    _id = next(_id_generator)
    _data[_id] = Cart(id=_id)

    return _data[_id]


def get_one(_id: int) -> Cart | None:
    if _id not in _data:
        return None

    return _data[_id].model_copy(deep=True)


def sum_quantities(cart: Cart) -> int:
    result = 0
    for item in cart.items:
        result += item.quantity

    return result


def get_many(
        offset: int = 0,
        limit: int = 10,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        min_quantity: int | None = None,
        max_quantity: int | None = None,
) -> Iterable[Cart]:
    curr = 0
    yielded_count = 0
    for cart in _data.values():
        if yielded_count >= limit:
            break

        total_quantity = sum_quantities(cart)

        if (min_price is None or cart.price >= min_price) \
                and (max_price is None or cart.price <= max_price) \
                and (min_quantity is None or total_quantity >= min_quantity) \
                and (max_quantity is None or total_quantity <= max_quantity):
            if curr >= offset:
                yield cart.model_copy(deep=True)
                yielded_count += 1

            curr += 1

def save(cart: Cart) -> None:
    _data[cart.id] = cart
