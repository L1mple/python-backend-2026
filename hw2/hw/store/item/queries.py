from decimal import Decimal
from typing import Iterator

from store.general import int_id_generator
from store.item.models import (
    ItemInfo,
    ItemEntity,
    PatchItemInfo
)

_data = dict[int, ItemInfo]()

_id_generator = int_id_generator()


def add(info: ItemInfo) -> ItemEntity:
    _id = next(_id_generator)
    _data[_id] = info

    return ItemEntity(id=_id, **info.model_dump())


def delete(_id: int) -> None:
    if _id in _data:
        _data[_id].deleted = True


def get_one(_id: int) -> ItemEntity | None:
    if _id not in _data:
        return None

    _info = _data[_id]

    if _info.deleted:
        return None

    return ItemEntity(id=_id, **_info.model_dump())


def get_many(
        offset: int = 0,
        limit: int = 10,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        show_deleted: bool = False,
) -> Iterator[ItemEntity]:
    curr = 0
    yielded_count = 0
    for _id, _info in _data.items():
        if yielded_count >= limit:
            break

        if (show_deleted or not _info.deleted) \
                and (min_price is None or _info.price >= min_price) \
                and (max_price is None or _info.price <= max_price):
            if curr >= offset:
                yield ItemEntity(id=_id, **_info.model_dump())
                yielded_count += 1

            curr += 1


def update(_id: int, _info: ItemInfo) -> ItemEntity | None:
    if _id not in _data:
        return None

    _data[_id] = _info

    return ItemEntity(id=_id, **_info.model_dump())


def patch(_id: int, _patch_info: PatchItemInfo) -> ItemEntity | None:
    if _id not in _data:
        return None

    item = _data[_id]

    if item.deleted:
        return None

    update_data = _patch_info.model_dump(exclude_unset=True)

    updated_item = item.model_copy(update=update_data)

    _data[_id] = updated_item

    return ItemEntity(id=_id, **updated_item.model_dump())
