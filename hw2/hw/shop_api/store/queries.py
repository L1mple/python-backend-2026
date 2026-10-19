from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shop_api.store.models import Cart, CartItem, Item


async def add_item(session: AsyncSession, name: str, price: float) -> Item:
    item = Item(
        name=name,
        price=price,
        description=None,
        in_stock=True,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def get_item(session: AsyncSession, item_id: int) -> Item | None:
    result = await session.execute(select(Item).where(Item.id == item_id))
    return result.scalar_one_or_none()


async def get_items(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> list[Item]:
    stmt = select(Item)

    if not show_deleted:
        stmt = stmt.where(Item.in_stock.is_(True))
    if min_price is not None:
        stmt = stmt.where(Item.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Item.price <= max_price)

    stmt = stmt.order_by(Item.id).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_item(
    session: AsyncSession, item_id: int, name: str, price: float
) -> Item | None:
    item = await get_item(session, item_id)
    if item is None:
        return None

    item.name = name
    item.price = price
    await session.commit()
    await session.refresh(item)
    return item


async def patch_item(
    session: AsyncSession,
    item_id: int,
    name: str | None = None,
    price: float | None = None,
) -> Item | None:
    item = await get_item(session, item_id)
    if item is None:
        return None

    if name is not None:
        item.name = name
    if price is not None:
        item.price = price

    await session.commit()
    await session.refresh(item)
    return item


async def delete_item(session: AsyncSession, item_id: int) -> None:
    item = await get_item(session, item_id)
    if item is None:
        return

    item.in_stock = False
    await session.commit()


async def add_cart(session: AsyncSession) -> Cart:
    cart = Cart(
        email=f"cart-{uuid4().hex}@example.com",
        name=f"cart-{uuid4().hex}",
        age=0,
    )
    session.add(cart)
    await session.commit()
    await session.refresh(cart)
    return cart


async def get_cart(session: AsyncSession, cart_id: int) -> Cart | None:
    result = await session.execute(select(Cart).where(Cart.id == cart_id))
    return result.scalar_one_or_none()


async def get_cart_items(
    session: AsyncSession, cart_id: int
) -> list[tuple[Item, int]]:
    stmt = (
        select(Item, CartItem.quantity)
        .join(CartItem, CartItem.item_id == Item.id)
        .where(CartItem.cart_id == cart_id)
        .order_by(Item.id)
    )
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def get_all_carts(session: AsyncSession) -> list[Cart]:
    result = await session.execute(select(Cart).order_by(Cart.id))
    return list(result.scalars().all())


async def add_item_to_cart(
    session: AsyncSession, cart_id: int, item_id: int
) -> bool:
    cart = await get_cart(session, cart_id)
    if cart is None:
        return False

    item = await get_item(session, item_id)
    if item is None:
        return False

    result = await session.execute(
        select(CartItem).where(
            CartItem.cart_id == cart_id,
            CartItem.item_id == item_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        session.add(
            CartItem(
                cart_id=cart_id,
                item_id=item_id,
                quantity=1,
                total_price=float(item.price),
                status="pending",
            )
        )
    else:
        existing.quantity += 1
        existing.total_price = float(item.price) * existing.quantity

    await session.commit()
    return True