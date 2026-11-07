from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shop_api.models import Cart, CartItem, Item


async def add_item(session: AsyncSession, name: str, price: float) -> Item:
    item = Item(name=name, price=price)
    session.add(item)
    await session.commit()
    return item


async def get_item(
    session: AsyncSession,
    item_id: int,
    *,
    for_update: bool = False,
) -> Item | None:
    # for_update: строка блокируется до конца транзакции, чтобы параллельный
    # запрос не изменил товар между проверкой и записью
    return await session.get(Item, item_id, with_for_update=for_update)


async def list_items(
    session: AsyncSession,
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    show_deleted: bool,
) -> list[Item]:
    query = select(Item).order_by(Item.id).offset(offset).limit(limit)

    if not show_deleted:
        query = query.where(Item.deleted.is_(False))
    if min_price is not None:
        query = query.where(Item.price >= min_price)
    if max_price is not None:
        query = query.where(Item.price <= max_price)

    return list(await session.scalars(query))


async def add_cart(session: AsyncSession) -> Cart:
    cart = Cart(items=[])
    session.add(cart)
    await session.commit()
    return cart


async def get_cart(session: AsyncSession, cart_id: int) -> Cart | None:
    return await session.get(Cart, cart_id)


async def list_carts(
    session: AsyncSession,
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    min_quantity: int | None,
    max_quantity: int | None,
) -> list[Cart]:
    # Сумма и количество считаются в БД, фильтры идут в HAVING,
    # поэтому OFFSET и LIMIT применяются уже к отфильтрованным корзинам
    price = func.coalesce(
        func.sum(case((Item.deleted.is_(False), Item.price * CartItem.quantity), else_=0.0)),
        0.0,
    )
    quantity = func.coalesce(func.sum(CartItem.quantity), 0)

    query = (
        select(Cart)
        .outerjoin(CartItem, CartItem.cart_id == Cart.id)
        .outerjoin(Item, Item.id == CartItem.item_id)
        .group_by(Cart.id)
        .order_by(Cart.id)
        .offset(offset)
        .limit(limit)
    )

    if min_price is not None:
        query = query.having(price >= min_price)
    if max_price is not None:
        query = query.having(price <= max_price)
    if min_quantity is not None:
        query = query.having(quantity >= min_quantity)
    if max_quantity is not None:
        query = query.having(quantity <= max_quantity)

    return list(await session.scalars(query))


async def add_to_cart(session: AsyncSession, cart: Cart, item: Item) -> None:
    # Одна команда вместо «прочитать количество, прибавить, записать»:
    # два одновременных добавления не потеряют друг друга
    query = (
        insert(CartItem)
        .values(cart_id=cart.id, item_id=item.id, quantity=1)
        .on_conflict_do_update(
            index_elements=[CartItem.cart_id, CartItem.item_id],
            set_={"quantity": CartItem.quantity + 1},
        )
    )
    await session.execute(query)
    await session.commit()
    await session.refresh(cart)
