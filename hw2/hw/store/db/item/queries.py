from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from store.db.item.models import Item
from store.item.models import (
    ItemInfo,
    ItemEntity,
    PatchItemInfo,
)


def _to_entity(orm: Item) -> ItemEntity:
    return ItemEntity(
        id=orm.id,
        name=orm.name,
        price=Decimal(str(orm.price)),
        deleted=orm.is_deleted,
    )


async def add(session: AsyncSession, info: ItemInfo) -> ItemEntity:
    orm = Item(
        name=info.name,
        price=float(info.price),
        is_deleted=info.deleted,
    )
    session.add(orm)
    await session.commit()
    await session.refresh(orm)

    return _to_entity(orm)


async def delete(session: AsyncSession, _id: int) -> None:
    orm = await session.get(Item, _id)
    if orm is None:
        return

    orm.is_deleted = True
    await session.commit()


async def get_one(session: AsyncSession, _id: int) -> ItemEntity | None:
    orm = await session.get(Item, _id)

    if orm is None or orm.is_deleted:
        return None

    return _to_entity(orm)


async def get_many(
        session: AsyncSession,
        offset: int = 0,
        limit: int = 10,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        show_deleted: bool = False,
) -> list[ItemEntity]:
    stmt = select(Item)

    if not show_deleted:
        stmt = stmt.where(Item.is_deleted.is_(False))
    if min_price is not None:
        stmt = stmt.where(Item.price >= float(min_price))
    if max_price is not None:
        stmt = stmt.where(Item.price <= float(max_price))

    stmt = stmt.order_by(Item.id).offset(offset).limit(limit)

    result = await session.execute(stmt)

    return [_to_entity(orm) for orm in result.scalars().all()]


async def update(
        session: AsyncSession,
        _id: int,
        info: ItemInfo,
) -> ItemEntity | None:
    orm = await session.get(Item, _id)
    if orm is None:
        return None

    orm.name = info.name
    orm.price = float(info.price)
    orm.is_deleted = info.deleted

    await session.commit()
    await session.refresh(orm)

    return _to_entity(orm)


async def patch(
        session: AsyncSession,
        _id: int,
        patch_info: PatchItemInfo,
) -> ItemEntity | None:
    orm = await session.get(Item, _id)
    if orm is None or orm.is_deleted:
        return None

    data = patch_info.model_dump(exclude_unset=True)

    if "name" in data:
        orm.name = data["name"]
    if "price" in data:
        orm.price = float(data["price"])

    await session.commit()
    await session.refresh(orm)

    return _to_entity(orm)
