from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from shop_api import metrics, storage
from shop_api.contracts import CartCreatedResponse, CartItemResponse, CartResponse
from shop_api.db import SessionDep
from shop_api.models import Cart

router = APIRouter(prefix="/cart", tags=["cart"])


def _cart_response(cart: Cart) -> CartResponse:
    items = []
    price = 0.0

    for cart_item in cart.items:
        item = cart_item.item
        items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=cart_item.quantity,
                available=not item.deleted,
            )
        )
        # Удалённый товар купить нельзя, в сумму он не входит
        if not item.deleted:
            price += item.price * cart_item.quantity

    return CartResponse(id=cart.id, items=items, price=price)


async def _get_cart_or_404(session: AsyncSession, cart_id: int) -> Cart:
    cart = await storage.get_cart(session, cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")
    return cart


@router.post("", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response, session: SessionDep) -> CartCreatedResponse:
    cart = await storage.add_cart(session)
    metrics.CARTS_CREATED.inc()
    response.headers["location"] = f"/cart/{cart.id}"
    return CartCreatedResponse(id=cart.id)


@router.get("/{cart_id}")
async def get_cart(cart_id: int, session: SessionDep) -> CartResponse:
    return _cart_response(await _get_cart_or_404(session, cart_id))


@router.get("")
async def list_carts(
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[CartResponse]:
    carts = await storage.list_carts(
        session,
        offset,
        limit,
        min_price,
        max_price,
        min_quantity,
        max_quantity,
    )
    return [_cart_response(cart) for cart in carts]


@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int, session: SessionDep) -> CartResponse:
    cart = await _get_cart_or_404(session, cart_id)

    item = await storage.get_item(session, item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")

    await storage.add_to_cart(session, cart, item)
    metrics.CART_ITEMS_ADDED.inc()
    return _cart_response(cart)
