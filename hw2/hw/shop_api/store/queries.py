from sqlalchemy import Select, Subquery, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from .models import Cart, CartItem, CartWithPrice, Item


async def add_item(session: AsyncSession, name: str, price: float) -> Item:
    item = Item(name=name, price=price)
    session.add(item)
    await session.commit()
    return item


async def get_item(session: AsyncSession, id: int) -> Item | None:
    return await session.get(Item, id)


async def get_items(
    session: AsyncSession,
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    show_deleted: bool,
) -> list[Item]:
    query = select(Item).order_by(Item.id)

    if not show_deleted:
        query = query.where(Item.deleted.is_(False))

    if min_price is not None:
        query = query.where(Item.price >= min_price)

    if max_price is not None:
        query = query.where(Item.price <= max_price)

    items = await session.scalars(query.offset(offset).limit(limit))
    return list(items)


async def update_item(
    session: AsyncSession,
    id: int,
    name: str,
    price: float,
) -> Item | None:
    item = await session.get(Item, id)

    if item is None or item.deleted:
        return None

    item.name = name
    item.price = price
    await session.commit()

    return item


async def patch_item(
    session: AsyncSession,
    id: int,
    name: str | None,
    price: float | None,
) -> Item | None:
    item = await session.get(Item, id)

    if item is None or item.deleted:
        return None

    if name is not None:
        item.name = name

    if price is not None:
        item.price = price

    await session.commit()

    return item


async def delete_item(session: AsyncSession, id: int) -> None:
    item = await session.get(Item, id)

    if item is not None and not item.deleted:
        item.deleted = True
        await session.commit()


async def add_cart(session: AsyncSession) -> Cart:
    cart = Cart()
    session.add(cart)
    await session.commit()
    return cart


def _cart_totals() -> Subquery:
    return (
        select(
            CartItem.cart_id.label("cart_id"),
            func.sum(CartItem.quantity).label("quantity"),
            func.sum(
                case(
                    (Item.deleted.is_(False), CartItem.quantity * Item.price),
                    else_=0.0,
                )
            ).label("price"),
        )
        .join(Item, Item.id == CartItem.item_id)
        .group_by(CartItem.cart_id)
        .subquery()
    )


def _select_carts_with_price(totals: Subquery) -> Select:
    return (
        select(Cart, func.coalesce(totals.c.price, 0.0))
        .outerjoin(totals, totals.c.cart_id == Cart.id)
        .options(selectinload(Cart.items).joinedload(CartItem.item))
        .execution_options(populate_existing=True)
    )


async def get_cart(session: AsyncSession, id: int) -> CartWithPrice | None:
    totals = _cart_totals()
    query = _select_carts_with_price(totals).where(Cart.id == id)

    row = (await session.execute(query)).one_or_none()

    if row is None:
        return None

    cart, price = row
    return CartWithPrice(cart=cart, price=price)


async def get_carts(
    session: AsyncSession,
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    min_quantity: int | None,
    max_quantity: int | None,
) -> list[CartWithPrice]:
    totals = _cart_totals()
    total_price = func.coalesce(totals.c.price, 0.0)
    total_quantity = func.coalesce(totals.c.quantity, 0)

    query = _select_carts_with_price(totals).order_by(Cart.id)

    if min_price is not None:
        query = query.where(total_price >= min_price)

    if max_price is not None:
        query = query.where(total_price <= max_price)

    if min_quantity is not None:
        query = query.where(total_quantity >= min_quantity)

    if max_quantity is not None:
        query = query.where(total_quantity <= max_quantity)

    rows = (await session.execute(query.offset(offset).limit(limit))).all()
    return [CartWithPrice(cart=cart, price=price) for cart, price in rows]


async def add_item_to_cart(
    session: AsyncSession,
    cart_id: int,
    item_id: int,
) -> CartWithPrice | None:
    cart = await session.get(Cart, cart_id)
    item = await session.get(Item, item_id)

    if cart is None or item is None or item.deleted:
        return None

    cart_item = await session.get(CartItem, (cart_id, item_id))

    if cart_item is None:
        session.add(CartItem(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        cart_item.quantity += 1

    await session.commit()

    return await get_cart(session, cart_id)
