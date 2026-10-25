from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from shop_api.models import Item, Cart, CartItem
from shop_api.contracts import Cart as CartResponse, CartItem as CartItemResponse


async def create_cart(session: AsyncSession) -> Cart:
    cart = Cart()
    session.add(cart)
    await session.flush()
    return cart


async def get_cart(session: AsyncSession, cart_id: int) -> Cart | None:
    result = await session.execute(
        select(Cart)
        .options(selectinload(Cart.cart_items).selectinload(CartItem.item))
        .where(Cart.id == cart_id)
    )
    return result.scalar_one_or_none()


def build_cart_response(session: AsyncSession, cart: Cart) -> CartResponse:
    cart_items = []
    total_price = 0.0
    for ci in cart.cart_items:
        item = ci.item
        if item is None:
            continue
        cart_items.append(CartItemResponse(
            id=item.id,
            name=item.name,
            quantity=ci.quantity,
            available=not item.deleted,
        ))
        total_price += float(item.price) * ci.quantity
    return CartResponse(
        id=cart.id,
        items=cart_items,
        price=total_price,
    )


async def add_item_to_cart(session: AsyncSession, cart_id: int, item_id: int) -> CartResponse:
    cart_result = await session.execute(
        select(Cart)
        .options(selectinload(Cart.cart_items).selectinload(CartItem.item))
        .where(Cart.id == cart_id)
    )
    cart = cart_result.scalar_one_or_none()
    if cart is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found",
        )
    item_result = await session.execute(select(Item).where(Item.id == item_id))
    item = item_result.scalar_one_or_none()
    if item is None or item.deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    ci_result = await session.execute(
        select(CartItem).where(
            CartItem.cart_id == cart_id,
            CartItem.item_id == item_id
        )
    )
    ci = ci_result.scalar_one_or_none()
    if ci is None:
        ci = CartItem(cart_id=cart_id, item_id=item_id, quantity=1)
        session.add(ci)
        await session.flush()
        await session.refresh(cart, attribute_names=["cart_items"])
    else:
        ci.quantity += 1
    return build_cart_response(session, cart)


async def get_carts(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> list[CartResponse]:
    result = await session.execute(
        select(Cart)
        .options(selectinload(Cart.cart_items).selectinload(CartItem.item))
        .offset(offset)
        .limit(limit)
    )
    carts = result.scalars().all()
    responses = []
    for cart in carts:
        resp = build_cart_response(session, cart)
        if min_price is not None and resp.price < min_price:
            continue
        if max_price is not None and resp.price > max_price:
            continue
        total_quantity = sum(it.quantity for it in resp.items)
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue
        responses.append(resp)
    return responses


async def create_item(session: AsyncSession, name: str, price: float) -> Item:
    item = Item(name=name, price=price, deleted=False)
    session.add(item)
    await session.flush()
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
    conditions = []
    if not show_deleted:
        conditions.append(Item.deleted == False)
    if min_price is not None:
        conditions.append(Item.price >= min_price)
    if max_price is not None:
        conditions.append(Item.price <= max_price)
    where_clause = and_(*conditions) if conditions else True
    result = await session.execute(select(Item).where(where_clause).offset(offset).limit(limit))
    return result.scalars().all()


async def update_item(session: AsyncSession, item_id: int, name: str, price: float) -> Item:
    result = await session.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item is None or item.deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    item.name = name
    item.price = price
    return item


async def patch_item(session: AsyncSession, item_id: int, update_data: dict) -> tuple[Item, bool]:
    result = await session.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    if item.deleted:
        return item, True
    if "name" in update_data:
        item.name = update_data["name"]
    if "price" in update_data:
        item.price = update_data["price"]
    return item, False


async def soft_delete_item(session: AsyncSession, item_id: int) -> bool:
    result = await session.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    if not item.deleted:
        item.deleted = True
    return True
