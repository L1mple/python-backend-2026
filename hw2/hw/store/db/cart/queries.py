from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from store.cart.models import Cart, CartItem
from store.db.cart.models import Cart as CartORM
from store.db.cart.models import CartItem as CartItemORM
from store.item.models import ItemEntity


def _to_domain(orm: CartORM) -> Cart:
    return Cart(
        id=orm.id,
        items=[
            CartItem(
                item=ItemEntity(
                    id=cart_item.item.id,
                    name=cart_item.item.name,
                    price=Decimal(str(cart_item.item.price)),
                    deleted=cart_item.item.is_deleted,
                ),
                quantity=cart_item.quantity,
            )
            for cart_item in orm.items
        ],
    )


def _carts_with_items():
    return select(CartORM).options(
        selectinload(CartORM.items).selectinload(CartItemORM.item)
    )


async def add(session: AsyncSession) -> Cart:
    orm = CartORM()
    session.add(orm)
    await session.commit()
    await session.refresh(orm)

    return _to_domain(orm)


async def get_one(session: AsyncSession, _id: int) -> Cart | None:
    stmt = _carts_with_items().where(CartORM.id == _id)
    result = await session.execute(stmt)
    orm = result.scalar_one_or_none()

    if orm is None:
        return None

    return _to_domain(orm)


async def get_many(
        session: AsyncSession,
        offset: int = 0,
        limit: int = 10,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        min_quantity: int | None = None,
        max_quantity: int | None = None,
) -> list[Cart]:
    result = await session.execute(_carts_with_items().order_by(CartORM.id))

    filtered: list[Cart] = []
    for cart in (_to_domain(orm) for orm in result.scalars().all()):
        total_quantity = sum(item.quantity for item in cart.items)

        if (min_price is None or cart.price >= min_price) \
                and (max_price is None or cart.price <= max_price) \
                and (min_quantity is None or total_quantity >= min_quantity) \
                and (max_quantity is None or total_quantity <= max_quantity):
            filtered.append(cart)

    return filtered[offset:offset + limit]


async def add_item(
        session: AsyncSession,
        cart_id: int,
        item_id: int,
        quantity: int = 1,
) -> Cart | None:
    cart = await session.get(CartORM, cart_id)
    if cart is None:
        return None

    stmt = select(CartItemORM).where(
        CartItemORM.cart_id == cart_id,
        CartItemORM.item_id == item_id,
    )
    result = await session.execute(stmt)
    cart_item = result.scalar_one_or_none()

    if cart_item is None:
        session.add(
            CartItemORM(cart_id=cart_id, item_id=item_id, quantity=quantity)
        )
    else:
        cart_item.quantity += quantity

    await session.commit()

    return await get_one(session, cart_id)
