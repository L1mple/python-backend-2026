from __future__ import annotations

from typing import Iterable

from sqlalchemy import select

from store.db import SessionLocal
from store.item.models import ItemEntity, ItemOrm


def add(name: str, price: float) -> ItemEntity:
    with SessionLocal.begin() as session:
        item = ItemOrm(name=name, price=price)
        session.add(item)
        session.flush()
        return item.to_entity()


def get(item_id: int) -> ItemEntity | None:
    with SessionLocal() as session:
        item = session.get(ItemOrm, item_id)
        return item.to_entity() if item is not None else None


def get_many(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> Iterable[ItemEntity]:
    query = select(ItemOrm)
    if not show_deleted:
        query = query.where(ItemOrm.deleted.is_(False))
    if min_price is not None:
        query = query.where(ItemOrm.price >= min_price)
    if max_price is not None:
        query = query.where(ItemOrm.price <= max_price)
    query = query.order_by(ItemOrm.id).offset(offset).limit(limit)

    with SessionLocal() as session:
        return [item.to_entity() for item in session.scalars(query)]


def replace(item_id: int, name: str, price: float) -> ItemEntity | None:
    return patch(item_id, name=name, price=price)


def patch(
    item_id: int,
    name: str | None = None,
    price: float | None = None,
) -> ItemEntity | None:
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, item_id)
        if item is None:
            return None
        if name is not None:
            item.name = name
        if price is not None:
            item.price = price
        return item.to_entity()


def delete(item_id: int) -> ItemEntity | None:
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, item_id)
        if item is None:
            return None
        item.deleted = True
        return item.to_entity()
