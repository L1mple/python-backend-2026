from itertools import islice
from typing import Iterable, Iterator

from .models import (
    CartEntity,
    CartInfo,
    CartItem,
    ItemEntity,
    ItemInfo,
    PatchItemInfo,
)

_items = dict[int, ItemInfo]()
_carts = dict[int, CartInfo]()


def int_id_generator() -> Iterator[int]:
    i = 0
    while True:
        yield i
        i += 1


_item_id_generator = int_id_generator()
_cart_id_generator = int_id_generator()


# ---------------------------------------------------------------- items


def add_item(info: ItemInfo) -> ItemEntity:
    id = next(_item_id_generator)
    _items[id] = info

    return ItemEntity(id, info)


def get_item(id: int) -> ItemEntity | None:
    """Возвращает товар, даже если он помечен удаленным.

    Отфильтровать удаленный товар — ответственность ручки: корзине он нужен,
    чтобы показать позицию как недоступную.
    """
    info = _items.get(id)

    if info is None:
        return None

    return ItemEntity(id, info)


def get_many_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> Iterable[ItemEntity]:
    matched = (
        ItemEntity(id, info)
        for id, info in _items.items()
        if (show_deleted or not info.deleted)
        and (min_price is None or info.price >= min_price)
        and (max_price is None or info.price <= max_price)
    )

    return _paginate(matched, offset, limit)


def update_item(id: int, info: ItemInfo) -> ItemEntity | None:
    """Полная замена существующего товара; создание новых запрещено."""
    stored = _items.get(id)

    if stored is None or stored.deleted:
        return None

    # флаг deleted не является частью представления товара и не заменяется
    info.deleted = stored.deleted
    _items[id] = info

    return ItemEntity(id, info)


def patch_item(id: int, patch_info: PatchItemInfo) -> ItemEntity | None:
    info = _items.get(id)

    if info is None or info.deleted:
        return None

    if patch_info.name is not None:
        info.name = patch_info.name

    if patch_info.price is not None:
        info.price = patch_info.price

    return ItemEntity(id, info)


def delete_item(id: int) -> None:
    """Мягкое удаление: запись остается, чтобы корзины сохранили свои позиции."""
    info = _items.get(id)

    if info is not None:
        info.deleted = True


# ---------------------------------------------------------------- carts


def add_cart() -> CartEntity:
    id = next(_cart_id_generator)
    _carts[id] = CartInfo()

    return _as_cart_entity(id, _carts[id])


def get_cart(id: int) -> CartEntity | None:
    info = _carts.get(id)

    if info is None:
        return None

    return _as_cart_entity(id, info)


def get_many_carts(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> Iterable[CartEntity]:
    matched = (
        entity
        for entity in (_as_cart_entity(id, info) for id, info in _carts.items())
        if (min_price is None or entity.price >= min_price)
        and (max_price is None or entity.price <= max_price)
        and (min_quantity is None or entity.quantity >= min_quantity)
        and (max_quantity is None or entity.quantity <= max_quantity)
    )

    return _paginate(matched, offset, limit)


def add_item_to_cart(cart_id: int, item_id: int) -> CartEntity | None:
    """Кладет товар в корзину, увеличивая количество, если он там уже есть."""
    info = _carts.get(cart_id)

    if info is None or item_id not in _items:
        return None

    info.items[item_id] = info.items.get(item_id, 0) + 1

    return _as_cart_entity(cart_id, info)


# ---------------------------------------------------------------- helpers


def _as_cart_entity(id: int, info: CartInfo) -> CartEntity:
    """Собирает представление корзины из актуальных данных товаров."""
    items = []
    price = 0.0

    for item_id, quantity in info.items.items():
        item_info = _items[item_id]

        items.append(
            CartItem(
                id=item_id,
                name=item_info.name,
                quantity=quantity,
                available=not item_info.deleted,
            )
        )
        price += item_info.price * quantity

    return CartEntity(id=id, items=items, price=price)


def _paginate[T](entities: Iterable[T], offset: int, limit: int) -> list[T]:
    return list(islice(entities, offset, offset + limit))
