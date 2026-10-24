
from sqlalchemy import select

from .database import SessionLocal
from .models import ItemEntity, ItemInfo, PatchItemInfo
from .orm_models import ItemOrm


def to_entity(item: ItemOrm) -> ItemEntity:
    return ItemEntity(
        id=item.id,
        info=ItemInfo(
            name=item.name,
            price=float(item.price),
            deleted=item.deleted,
        ),
    )


def add(info: ItemInfo) -> ItemEntity:
    with SessionLocal.begin() as session:
        item = ItemOrm(
            name=info.name,
            price=info.price,
            deleted=info.deleted,
        )

        session.add(item)
        session.flush()

        return to_entity(item)


def get_one(id: int) -> ItemEntity | None:
    with SessionLocal() as session:
        item = session.get(ItemOrm, id)

        if item is None:
            return None

        return to_entity(item)


def get_many(
        offset: int = 0,
        limit: int = 10,
        min_price: float | None = None,
        max_price: float | None = None,
        show_deleted: bool = False,
) -> list[ItemEntity]:
    with SessionLocal() as session:
        query = select(ItemOrm)

        if not show_deleted:
            query = query.where(ItemOrm.deleted.is_(False))

        if min_price is not None:
            query = query.where(ItemOrm.price >= min_price)

        if max_price is not None:
            query = query.where(ItemOrm.price <= max_price)

        query = (
            query.order_by(ItemOrm.id)
            .offset(offset)
            .limit(limit)
        )

        items = session.scalars(query).all()

        return [to_entity(item) for item in items]


def update(id: int, info: ItemInfo) -> ItemEntity | None:
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, id)

        if item is None:
            return None

        item.name = info.name
        item.price = info.price
        item.deleted = info.deleted

        session.flush()

        return to_entity(item)


def patch(
        id: int,
        patch_info: PatchItemInfo,
) -> ItemEntity | None:
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, id)

        if item is None or item.deleted:
            return None

        if patch_info.name is not None:
            item.name = patch_info.name

        if patch_info.price is not None:
            item.price = patch_info.price

        session.flush()

        return to_entity(item)


def delete(id: int) -> None:
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, id)

        if item is not None:
            item.deleted = True
