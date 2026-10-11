from __future__ import annotations

from itertools import count
from typing import Iterable

from store.item.models import ItemEntity

_items: dict[int, ItemEntity] = {}
_id_generator = count(start=1)


def add(name: str, price: float) -> ItemEntity:
    item_id = next(_id_generator)
    entity = ItemEntity(id=item_id, name=name, price=price, deleted=False)
    _items[item_id] = entity
    return entity


def get(item_id: int) -> ItemEntity | None:
    return _items.get(item_id)


def get_many(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> Iterable[ItemEntity]:
    result = []
    for entity in _items.values():
        if not show_deleted and entity.deleted:
            continue
        if min_price is not None and entity.price < min_price:
            continue
        if max_price is not None and entity.price > max_price:
            continue
        result.append(entity)
    return result[offset : offset + limit]


def replace(item_id: int, name: str, price: float) -> ItemEntity | None:
    entity = _items.get(item_id)
    if entity is None:
        return None
    entity.name = name
    entity.price = price
    return entity


def patch(
    item_id: int,
    name: str | None = None,
    price: float | None = None,
) -> ItemEntity | None:
    entity = _items.get(item_id)
    if entity is None:
        return None
    if name is not None:
        entity.name = name
    if price is not None:
        entity.price = price
    return entity


def delete(item_id: int) -> ItemEntity | None:
    entity = _items.get(item_id)
    if entity is not None:
        entity.deleted = True
    return entity
