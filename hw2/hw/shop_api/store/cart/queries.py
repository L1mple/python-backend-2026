from sqlalchemy import select
from sqlalchemy.orm import selectinload

from shop_api.database import CartItemTable, CartTable, ItemTable, SessionFactory
from shop_api.store.cart.models import CartItem, CartInfo, CartEntity
from shop_api.store.item.models import ItemInfo, ItemEntity


def _to_entity(row: CartTable) -> CartEntity:
    items = [
        CartItem(
            info=ItemEntity(
                id=cart_item.item.id,
                info=ItemInfo(
                    name=cart_item.item.name,
                    price=cart_item.item.price,
                    deleted=cart_item.item.deleted,
                ),
            ),
            quantity=cart_item.quantity,
        )
        for cart_item in row.items
    ]
    return CartEntity(row.id, CartInfo(items=items, price=row.total_price))


async def add() -> int:
    async with SessionFactory() as session:
        cart = CartTable(total_price=0.0)
        session.add(cart)
        await session.commit()
        await session.refresh(cart)
        return cart.id


async def get_one(id: int) -> CartEntity | None:
    statement = (
        select(CartTable)
        .where(CartTable.id == id)
        .options(selectinload(CartTable.items).joinedload(CartItemTable.item))
    )
    async with SessionFactory() as session:
        row = (await session.scalars(statement)).unique().one_or_none()
        return _to_entity(row) if row is not None else None


async def get_many(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> list[CartEntity]:
    statement = (
        select(CartTable)
        .order_by(CartTable.id)
        .options(selectinload(CartTable.items).joinedload(CartItemTable.item))
    )
    if min_price is not None:
        statement = statement.where(CartTable.total_price >= min_price)
    if max_price is not None:
        statement = statement.where(CartTable.total_price <= max_price)

    async with SessionFactory() as session:
        rows = (await session.scalars(statement)).unique().all()
        result = [_to_entity(row) for row in rows]

    if min_quantity is not None:
        result = [cart for cart in result if sum(item.quantity for item in cart.info.items) >= min_quantity]
    if max_quantity is not None:
        result = [cart for cart in result if sum(item.quantity for item in cart.info.items) <= max_quantity]
    return result[offset:offset + limit]


async def add_item(id: int, new_item: ItemEntity) -> CartEntity | None:
    async with SessionFactory() as session:
        cart = await session.get(CartTable, id)
        item = await session.get(ItemTable, new_item.id)
        if cart is None or item is None or item.deleted:
            return None

        cart_item = await session.get(CartItemTable, (id, new_item.id))
        if cart_item is None:
            cart_item = CartItemTable(cart_id=id, item_id=new_item.id, quantity=1)
            session.add(cart_item)
        else:
            cart_item.quantity += 1

        cart.total_price += item.price
        await session.commit()

    return await get_one(id)
