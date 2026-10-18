from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from ...store import (
    add_item_to_cart,
    create_cart,
    get_cart,
    get_carts,
    get_item_raw,
)
from .contracts import CartItemResponse, CartResponse

router = APIRouter(prefix="/cart")


def _to_cart_response(cart) -> CartResponse:
    items_response: list[CartItemResponse] = []
    total_price = 0.0

    for cart_item in cart.items:
        item = get_item_raw(cart_item.item_id)
        if item is None:
            continue
        items_response.append(
            CartItemResponse.from_parts(item, cart_item.quantity)
        )
        total_price += item.info.price * cart_item.quantity

    return CartResponse(id=cart.id, items=items_response, price=total_price)


@router.post("/", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response) -> dict[str, int]:
    entity = create_cart()
    response.headers["location"] = f"/cart/{entity.id}"
    return {"id": entity.id}


@router.get("/", response_model=list[CartResponse])
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    carts = get_carts(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
    )
    return [_to_cart_response(c) for c in carts]


@router.get("/{cart_id}")
async def get_cart_by_id(cart_id: int) -> CartResponse:
    cart = get_cart(cart_id)
    if cart is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Cart {cart_id} not found",
        )
    return _to_cart_response(cart)


@router.post("/{cart_id}/add/{item_id}", status_code=HTTPStatus.CREATED)
async def post_add_to_cart(cart_id: int, item_id: int) -> CartResponse:
    cart = add_item_to_cart(cart_id, item_id)
    if cart is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Cart {cart_id} or item {item_id} not found",
        )
    return _to_cart_response(cart)
