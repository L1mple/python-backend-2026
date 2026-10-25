from typing import Iterable, TypeVar, Callable
from collections import OrderedDict
from itertools import islice
from enum import Enum
from dataclasses import fields

from annotated_types import Predicate

from .models import (
    AddItemInfo,
    ItemInfo,
    ItemEntity,
    PatchItemInfo,
    CartEntity,
    CartPositionsInfo,
    CartInfo
)

_itemData = OrderedDict[int, ItemInfo]()

# ------ Item Logic -----------

def int_id_generator() -> Iterable[int]:
    i = 0
    while True:
        yield i
        i += 1

_id_generator = int_id_generator()

def add_item(add_item: AddItemInfo) -> ItemEntity:
    id = next(_id_generator)
    # generic field value transfer, assuming absent fields have default values
    item = ItemInfo(**{f.name: getattr(add_item, f.name) for f in fields(add_item)})
    _itemData[id] = item
    return ItemEntity(id=id, info=item)

def get_item(id: int) -> ItemEntity | None:
    if id in _itemData and not _itemData[id].deleted:
        return ItemEntity(id=id, info=_itemData[id])
    return None

T = TypeVar("T")
def _min_max_filters(field_name:str, min_value : T| None, max_value : T| None) -> list[Callable[[object], bool]]:
    filters = []
    if min_value is not None:
        filters.append(lambda x: getattr(x, field_name) >= min_value)
    if max_value is not None:
        filters.append(lambda x: getattr(x, field_name) <= max_value)
    return filters

def get_item_multiple(offset:int = 0,
                      limit:int = 10,
                      min_price:float|None = None,
                      max_price:float|None = None,
                      show_deleted:bool = False) -> Iterable[ItemEntity]:
    filters = _min_max_filters("price", min_price, max_price)
    if not show_deleted:
        filters.append(lambda item: not item.deleted)

    matched = (
        (id, item_info)
        for id, item_info in _itemData.items()
        if all(pred(item_info) for pred in filters)
    )
    for id, item_info in islice(matched, offset, offset + limit):
        yield ItemEntity(id=id, info=item_info)

def _mutate_same_name_fields(info : ItemInfo, new_info : AddItemInfo | PatchItemInfo, skip_none = True):
    for f in fields(new_info):
        value = getattr(new_info, f.name)
        if skip_none and value is None:
            continue
        setattr(info, f.name, value)

class MutateErrors(Enum):
    MISSING = 404
    DELETED = 304

def _mutate_item(id: int, new_info: AddItemInfo | PatchItemInfo, skip_none = True) -> ItemEntity | MutateErrors:
    if id not in _itemData:
        return MutateErrors.MISSING

    item_info = _itemData[id]
    if item_info.deleted:
        return MutateErrors.DELETED

    _mutate_same_name_fields(item_info, new_info, skip_none=skip_none)
    return ItemEntity(id=id, info=item_info)

def put_item(id: int, put_info: AddItemInfo) -> ItemEntity | MutateErrors:
    return _mutate_item(id, new_info=put_info, skip_none=False)


def patch_item(id:int, patch_info: PatchItemInfo) -> ItemEntity|MutateErrors:
    return _mutate_item(id, new_info=patch_info, skip_none=True)

def delete_item(id: int) -> None:
    if id in _itemData:
        _itemData[id].deleted = True

# ---------- Cart logic -----------

_cartData = OrderedDict[int, CartPositionsInfo]()

def add_cart() -> CartEntity:
    cart_entity = CartEntity(next(_id_generator))
    _cartData[cart_entity.id] = cart_entity.info.positions
    return cart_entity

# Unsafe!
def _get_cart_info(id: int) -> CartInfo:
    positions = _cartData[id]
    price: float = 0
    quantity: int = 0

    for item_id, item_quantity in positions.items():
        quantity += item_quantity
        price += _itemData[item_id].price * item_quantity

    return CartInfo(positions=positions, price=price, quantity=quantity)

def get_cart(id: int) -> CartEntity | None:
    if id in _cartData:
        return CartEntity(id=id, info=_get_cart_info(id))
    return None


def get_cart_multiple(offset:int = 0,
                      limit:int = 10,
                      min_price:float|None = None,
                      max_price:float|None = None,
                      min_quantity:int|None = None,
                      max_quantity:int|None = None,
                      ):

    filters = _min_max_filters("price", min_price, max_price)
    filters += _min_max_filters("quantity", min_quantity, max_quantity)

    # can be generalised, will do later?
    matched = (
        (id, cart_info)
        for id in _cartData
        for cart_info in (_get_cart_info(id),)
        if all(pred(cart_info) for pred in filters)
    )
    for id, cart_info in islice(matched, offset, offset + limit):
        yield CartEntity(id=id, info=cart_info)

class ItemInsertionResult(Enum):
    OK = 0
    CART_NOT_FOUND = 1
    ITEM_NOT_FOUND = 2

def insert_item_to_cart(cart_id: int, item_id: int) -> None | ItemInsertionResult:
    if cart_id not in _cartData:
        return ItemInsertionResult.CART_NOT_FOUND
    if item_id not in _itemData:
        return ItemInsertionResult.ITEM_NOT_FOUND

    _cartData[cart_id][item_id] = _cartData[cart_id].get(item_id, 0) + 1
    return ItemInsertionResult.OK