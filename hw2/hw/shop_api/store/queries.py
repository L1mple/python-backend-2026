from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .database import async_session_maker
from .models import (
    CartEntity,
    CartItemInfo,
    CartItemORM,
    CartORM,
    ItemEntity,
    ItemInfo,
    ItemORM,
    PatchItemInfo,
)


async def create_item(info: ItemInfo) -> ItemEntity:
    async with async_session_maker() as session:
        orm = ItemORM(name=info.name, price=info.price)
        session.add(orm)
        await session.commit()
        await session.refresh(orm)
        return ItemEntity(id=orm.id, info=info, deleted=orm.deleted)


async def get_item(item_id: int) -> ItemEntity | None:
    async with async_session_maker() as session:
        orm = await session.get(ItemORM, item_id)
        if orm is None or orm.deleted:
            return None
        return ItemEntity(
            id=orm.id,
            info=ItemInfo(name=orm.name, price=orm.price),
            deleted=orm.deleted,
        )


async def get_item_raw(item_id: int) -> ItemEntity | None:
    async with async_session_maker() as session:
        orm = await session.get(ItemORM, item_id)
        if orm is None:
            return None
        return ItemEntity(
            id=orm.id,
            info=ItemInfo(name=orm.name, price=orm.price),
            deleted=orm.deleted,
        )


async def get_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> list[ItemEntity]:
    async with async_session_maker() as session:
        stmt = select(ItemORM)
        if not show_deleted:
            stmt = stmt.where(ItemORM.deleted.is_(False))
        if min_price is not None:
            stmt = stmt.where(ItemORM.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(ItemORM.price <= max_price)
        stmt = stmt.offset(offset).limit(limit)
        result = await session.execute(stmt)
        return [
            ItemEntity(
                id=o.id, info=ItemInfo(name=o.name, price=o.price), deleted=o.deleted
            )
            for o in result.scalars().all()
        ]


async def update_item(item_id: int, info: ItemInfo) -> ItemEntity | None:
    async with async_session_maker() as session:
        orm = await session.get(ItemORM, item_id)
        if orm is None or orm.deleted:
            return None
        orm.name = info.name
        orm.price = info.price
        await session.commit()
        await session.refresh(orm)
        return ItemEntity(id=orm.id, info=info, deleted=orm.deleted)


async def patch_item(item_id: int, patch: PatchItemInfo) -> ItemEntity | None:
    async with async_session_maker() as session:
        orm = await session.get(ItemORM, item_id)
        if orm is None or orm.deleted:
            return None
        if patch.name is not None:
            orm.name = patch.name
        if patch.price is not None:
            orm.price = patch.price
        await session.commit()
        await session.refresh(orm)
        return ItemEntity(
            id=orm.id,
            info=ItemInfo(name=orm.name, price=orm.price),
            deleted=orm.deleted,
        )


async def delete_item(item_id: int) -> ItemEntity | None:
    async with async_session_maker() as session:
        orm = await session.get(ItemORM, item_id)
        if orm is None:
            return None
        orm.deleted = True
        await session.commit()
        return ItemEntity(
            id=orm.id,
            info=ItemInfo(name=orm.name, price=orm.price),
            deleted=True,
        )


async def create_cart() -> CartEntity:
    async with async_session_maker() as session:
        cart = CartORM()
        session.add(cart)
        await session.commit()
        await session.refresh(cart)
        return CartEntity(id=cart.id, items=[])


async def get_cart(cart_id: int) -> CartEntity | None:
    async with async_session_maker() as session:
        stmt = (
            select(CartORM)
            .where(CartORM.id == cart_id)
            .options(selectinload(CartORM.items))
        )
        result = await session.execute(stmt)
        cart = result.scalar_one_or_none()
        if cart is None:
            return None
        items = [
            CartItemInfo(item_id=ci.item_id, quantity=ci.quantity)
            for ci in cart.items
        ]
        return CartEntity(id=cart.id, items=items)


async def _cart_total_price(session: AsyncSession, cart_id: int) -> float:
    stmt = (
        select(func.sum(ItemORM.price * CartItemORM.quantity))
        .join(CartItemORM, CartItemORM.item_id == ItemORM.id)
        .where(CartItemORM.cart_id == cart_id)
    )
    result = await session.execute(stmt)
    return result.scalar() or 0.0


async def _cart_total_quantity(session: AsyncSession, cart_id: int) -> int:
    stmt = select(func.sum(CartItemORM.quantity)).where(
        CartItemORM.cart_id == cart_id
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_carts(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> list[CartEntity]:
    async with async_session_maker() as session:
        stmt = select(CartORM).options(selectinload(CartORM.items))
        result = await session.execute(stmt)
        carts = result.scalars().all()

        filtered: list[CartEntity] = []
        for cart in carts:
            price = await _cart_total_price(session, cart.id)
            quantity = await _cart_total_quantity(session, cart.id)
            if min_price is not None and price < min_price:
                continue
            if max_price is not None and price > max_price:
                continue
            if min_quantity is not None and quantity < min_quantity:
                continue
            if max_quantity is not None and quantity > max_quantity:
                continue
            items = [
                CartItemInfo(item_id=ci.item_id, quantity=ci.quantity)
                for ci in cart.items
            ]
            filtered.append(CartEntity(id=cart.id, items=items))

        return filtered[offset : offset + limit]


async def add_item_to_cart(cart_id: int, item_id: int) -> CartEntity | None:
    async with async_session_maker() as session:
        cart = await session.get(CartORM, cart_id)
        if cart is None:
            return None
        item = await session.get(ItemORM, item_id)
        if item is None or item.deleted:
            return None

        stmt = select(CartItemORM).where(
            CartItemORM.cart_id == cart_id,
            CartItemORM.item_id == item_id,
        )
        result = await session.execute(stmt)
        cart_item = result.scalar_one_or_none()

        if cart_item is not None:
            cart_item.quantity += 1
        else:
            session.add(
                CartItemORM(cart_id=cart_id, item_id=item_id, quantity=1)
            )

        await session.commit()

    return await get_cart(cart_id)
