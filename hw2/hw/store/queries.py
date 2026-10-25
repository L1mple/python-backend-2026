from typing import Iterable, TypeVar, Callable
from itertools import islice

from sqlalchemy.orm import Session

from .models import (
    AddItemInfo, CartEntity, CartInfo, CartPositionsInfo,
    ItemEntity, ItemInfo, PatchItemInfo,
    CartMapper, ItemMapper,
    CartOrm, CartPositionOrm, ItemOrm,
)


T = TypeVar("T")

def _min_max_filters(field_name: str, min_value: T | None, max_value: T | None):
    filters = []
    if min_value is not None:
        filters.append(lambda x: getattr(x, field_name) >= min_value)
    if max_value is not None:
        filters.append(lambda x: getattr(x, field_name) <= max_value)
    return filters


# ---------- Item logic ----------

def add_item(session: Session, add_item: AddItemInfo) -> ItemEntity:
    orm = ItemOrm(name=add_item.name, price=add_item.price, deleted=False)
    session.add(orm)
    session.flush()
    return ItemMapper.to_domain(orm)


def get_item(session: Session, id: int) -> ItemEntity | None:
    orm = session.query(ItemOrm).filter_by(id=id).first()
    if orm is None or orm.deleted:
        return None
    return ItemMapper.to_domain(orm)


def get_item_multiple(
    session: Session,
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> Iterable[ItemEntity]:
    q = session.query(ItemOrm)
    if not show_deleted:
        q = q.filter(ItemOrm.deleted.is_(False))
    if min_price is not None:
        q = q.filter(ItemOrm.price >= min_price)
    if max_price is not None:
        q = q.filter(ItemOrm.price <= max_price)
    q = q.order_by(ItemOrm.id).offset(offset).limit(limit)
    for orm in q.all():
        yield ItemMapper.to_domain(orm)


from enum import Enum

class MutateErrors(Enum):
    MISSING = 404
    DELETED = 304


def _mutate_same_name_fields(info: ItemInfo, new_info: AddItemInfo | PatchItemInfo, skip_none=True):
    from dataclasses import fields
    for f in fields(new_info):
        value = getattr(new_info, f.name)
        if skip_none and value is None:
            continue
        setattr(info, f.name, value)


def _mutate_item(
    session: Session,
    id: int,
    new_info: AddItemInfo | PatchItemInfo,
    skip_none: bool = True,
) -> ItemEntity | MutateErrors:
    orm = session.query(ItemOrm).filter_by(id=id).first()
    if orm is None:
        return MutateErrors.MISSING
    if orm.deleted:
        return MutateErrors.DELETED

    domain = ItemMapper.to_domain(orm)
    _mutate_same_name_fields(domain.info, new_info, skip_none=skip_none)

    orm.name = domain.info.name
    orm.price = domain.info.price
    orm.deleted = domain.info.deleted
    session.flush()
    return ItemMapper.to_domain(orm)


def put_item(session: Session, id: int, put_info: AddItemInfo) -> ItemEntity | MutateErrors:
    return _mutate_item(session, id, new_info=put_info, skip_none=False)


def patch_item(session: Session, id: int, patch_info: PatchItemInfo) -> ItemEntity | MutateErrors:
    return _mutate_item(session, id, new_info=patch_info, skip_none=True)


def delete_item(session: Session, id: int) -> None:
    orm = session.query(ItemOrm).filter_by(id=id).first()
    if orm is not None:
        orm.deleted = True
        session.flush()


# ---------- Cart logic ----------

def add_cart(session: Session) -> CartEntity:
    orm = CartOrm()
    session.add(orm)
    session.flush()
    return _get_cart_entity(session, orm.id)


def _item_lookup(session: Session):
    def lookup(item_id: int) -> ItemInfo:
        orm = session.query(ItemOrm).filter_by(id=item_id).first()
        return ItemInfo(name=orm.name, price=orm.price, deleted=orm.deleted)
    return lookup


def _get_cart_entity(session: Session, id: int) -> CartEntity:
    orm = session.query(CartOrm).filter_by(id=id).first()
    return CartMapper.to_domain(orm, _item_lookup(session))


def get_cart(session: Session, id: int) -> CartEntity | None:
    orm = session.query(CartOrm).filter_by(id=id).first()
    if orm is None:
        return None
    return CartMapper.to_domain(orm, _item_lookup(session))


def get_cart_multiple(
    session: Session,
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
):
    filters = _min_max_filters("price", min_price, max_price)
    filters += _min_max_filters("quantity", min_quantity, max_quantity)

    lookup = _item_lookup(session)
    matched = (
        CartMapper.to_domain(orm, lookup)
        for orm in session.query(CartOrm).order_by(CartOrm.id).all()
    )
    filtered = (cart for cart in matched if all(pred(cart.info) for pred in filters))
    yield from islice(filtered, offset, offset + limit)


class ItemInsertionResult(Enum):
    OK = 0
    CART_NOT_FOUND = 1
    ITEM_NOT_FOUND = 2


def insert_item_to_cart(session: Session, cart_id: int, item_id: int) -> ItemInsertionResult:
    cart = session.query(CartOrm).filter_by(id=cart_id).first()
    if cart is None:
        return ItemInsertionResult.CART_NOT_FOUND
    item = session.query(ItemOrm).filter_by(id=item_id).first()
    if item is None:
        return ItemInsertionResult.ITEM_NOT_FOUND

    pos = (
        session.query(CartPositionOrm)
        .filter_by(cart_id=cart_id, item_id=item_id)
        .first()
    )
    if pos is None:
        pos = CartPositionOrm(cart_id=cart_id, item_id=item_id, quantity=1)
        session.add(pos)
    else:
        pos.quantity += 1
    session.flush()
    return ItemInsertionResult.OK