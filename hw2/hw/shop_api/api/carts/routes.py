from http import HTTPStatus
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from shop_api import store
from shop_api.database import get_db
from .contracts import CartItemResponse, CartResponse

router = APIRouter(prefix="/cart", tags=["cart"])


async def _build_cart_response(
    session: AsyncSession, cart_id: int
) -> CartResponse:
    cart = await store.get_cart(session, cart_id)
    if cart is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /cart/{cart_id} was not found",
        )

    rows = await store.get_cart_items(session, cart_id)

    items: list[CartItemResponse] = []
    total_price = 0.0

    for item, quantity in rows:
        items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        total_price += float(item.price) * quantity

    return CartResponse(id=cart_id, items=items, price=total_price)


@router.post("/", status_code=HTTPStatus.CREATED)
async def post_cart(
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    cart = await store.add_cart(session)
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@router.get("/{id}")
async def get_cart_by_id(
    id: int,
    session: AsyncSession = Depends(get_db),
) -> CartResponse:
    return await _build_cart_response(session, id)


@router.get("/")
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    session: AsyncSession = Depends(get_db),
) -> list[CartResponse]:
    carts = await store.get_all_carts(session)

    result: list[CartResponse] = []

    for cart in carts:
        try:
            cart_response = await _build_cart_response(session, cart.id)
        except HTTPException:
            continue

        total_quantity = sum(item.quantity for item in cart_response.items)

        if min_price is not None and cart_response.price < min_price:
            continue
        if max_price is not None and cart_response.price > max_price:
            continue
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue

        result.append(cart_response)

    return result[offset : offset + limit]


@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(
    cart_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_db),
) -> CartResponse:
    ok = await store.add_item_to_cart(session, cart_id, item_id)

    if not ok:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Cart {cart_id} or item {item_id} was not found",
        )

    return await _build_cart_response(session, cart_id)