from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

import store
from store.models import CartEntity

from .contracts import (
    CartCreateResponse,
    CartItemResponse,
    CartResponse,
)


router = APIRouter(prefix="/cart")


def cart_to_response(
    cart: CartEntity,
) -> CartResponse:
    cart_items: list[CartItemResponse] = []

    price = 0.0

    for item_id, quantity in cart.info.items.items():
        item = store.get_one(item_id)

        if item is None:
            continue

        cart_items.append(
            CartItemResponse(
                id=item.id,
                name=item.info.name,
                quantity=quantity,
                available=not item.info.deleted,
            )
        )

        price += item.info.price * quantity

    return CartResponse(
        id=cart.id,
        items=cart_items,
        price=price,
    )


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
)
async def post_cart(
    response: Response,
) -> CartCreateResponse:
    cart = store.add_cart()

    response.headers["location"] = f"/cart/{cart.id}"

    return CartCreateResponse(
        id=cart.id,
    )


@router.get("")
async def get_cart_list(
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(gt=0),
    ] = 10,
    min_price: Annotated[
        float | None,
        Query(ge=0),
    ] = None,
    max_price: Annotated[
        float | None,
        Query(ge=0),
    ] = None,
    min_quantity: Annotated[
        int | None,
        Query(ge=0),
    ] = None,
    max_quantity: Annotated[
        int | None,
        Query(ge=0),
    ] = None,
) -> list[CartResponse]:
    result: list[CartResponse] = []

    for cart in store.get_all_carts():
        cart_response = cart_to_response(cart)

        quantity = sum(
            item.quantity
            for item in cart_response.items
        )

        if (
            min_price is not None
            and cart_response.price < min_price
        ):
            continue

        if (
            max_price is not None
            and cart_response.price > max_price
        ):
            continue

        if (
            min_quantity is not None
            and quantity < min_quantity
        ):
            continue

        if (
            max_quantity is not None
            and quantity > max_quantity
        ):
            continue

        result.append(cart_response)

    return result[offset : offset + limit]


@router.get("/{cart_id}")
async def get_cart(
    cart_id: int,
) -> CartResponse:
    cart = store.get_cart(cart_id)

    if cart is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Requested resource /cart/{cart_id} was not found",
        )

    return cart_to_response(cart)


@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(
    cart_id: int,
    item_id: int,
) -> Response:
    cart = store.get_cart(cart_id)
    item = store.get_one(item_id)

    if cart is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Requested resource /cart/{cart_id} was not found",
        )

    if item is None or item.info.deleted:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Requested resource /item/{item_id} was not found",
        )

    store.add_item_to_cart(
        cart_id,
        item_id,
    )

    return Response(
        status_code=HTTPStatus.OK,
    )