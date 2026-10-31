from typing import Iterable

from sqlalchemy import select

from shop_api.database import ItemTable, SessionFactory
from shop_api.store.item.models import ItemInfo, ItemEntity, PatchItemInfo


def _to_entity(row: ItemTable) -> ItemEntity:
    return ItemEntity(row.id, ItemInfo(row.name, row.price, row.deleted))


async def add(info: ItemInfo) -> ItemEntity:
    async with SessionFactory() as session:
        row = ItemTable(name=info.name, price=info.price, deleted=info.deleted)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _to_entity(row)


async def delete(id: int) -> bool:
    async with SessionFactory() as session:
        row = await session.get(ItemTable, id)
        if row is None:
            return False
        row.deleted = True
        await session.commit()
        return True


async def get_one(id: int) -> ItemEntity | None:
    async with SessionFactory() as session:
        row = await session.get(ItemTable, id)
        if row is None or row.deleted:
            return None
        return _to_entity(row)


async def get_many(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> list[ItemEntity]:
    statement = select(ItemTable).order_by(ItemTable.id).offset(offset).limit(limit)
    if min_price is not None:
        statement = statement.where(ItemTable.price >= min_price)
    if max_price is not None:
        statement = statement.where(ItemTable.price <= max_price)
    if not show_deleted:
        statement = statement.where(ItemTable.deleted.is_(False))

    async with SessionFactory() as session:
        rows = (await session.scalars(statement)).all()
        return [_to_entity(row) for row in rows]


async def update(id: int, info: ItemInfo) -> ItemEntity | None:
    async with SessionFactory() as session:
        row = await session.get(ItemTable, id)
        if row is None:
            return None
        row.name = info.name
        row.price = info.price
        await session.commit()
        await session.refresh(row)
        return _to_entity(row)


async def upsert(id: int, info: ItemInfo) -> ItemEntity:
    async with SessionFactory() as session:
        row = await session.get(ItemTable, id)
        if row is None:
            row = ItemTable(id=id, name=info.name, price=info.price, deleted=info.deleted)
            session.add(row)
        else:
            row.name = info.name
            row.price = info.price
            row.deleted = info.deleted
        await session.commit()
        await session.refresh(row)
        return _to_entity(row)


async def patch(id: int, patch_info: PatchItemInfo) -> ItemEntity | None:
    async with SessionFactory() as session:
        row = await session.get(ItemTable, id)
        if row is None or row.deleted:
            return None
        if patch_info.name is not None:
            row.name = patch_info.name
        if patch_info.price is not None:
            row.price = patch_info.price
        await session.commit()
        await session.refresh(row)
        return _to_entity(row)
