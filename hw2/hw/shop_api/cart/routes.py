from decimal import Decimal
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Response, Query, HTTPException

from shop_api.cart.contracts import CartResponse

import store.cart as cart_repo
import store.item as item_repo

router = APIRouter()


@router.post("", status_code=HTTPStatus.CREATED)
async def add_cart(response: Response) -> CartResponse:
    entity = cart_repo.add()

    response.headers["Location"] = f"/cart/{entity.id}"

    return CartResponse.from_entity(entity)


@router.get(
    "/{cart_id}",
    responses={
        HTTPStatus.OK: {
            "description": "Successfully returned requested cart",
        },
        HTTPStatus.NOT_FOUND: {
            "description": "Failed to return requested cart as one was not found",
        },
    },
)
async def get_cart(cart_id: int) -> CartResponse:
    entity = cart_repo.get_one(cart_id)
    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /cart/{cart_id} was not found",
        )
    return CartResponse.from_entity(entity)


@router.get("", status_code=HTTPStatus.OK)
async def get_cart_list(
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1)] = 10,
        min_price: Annotated[Decimal | None, Query(ge=0)] = None,
        max_price: Annotated[Decimal | None, Query(ge=0)] = None,
        min_quantity: Annotated[int | None, Query(ge=0)] = None,
        max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[CartResponse]:
    return [CartResponse.from_entity(e) for e in
            cart_repo.get_many(
                offset,
                limit,
                min_price,
                max_price,
                min_quantity,
                max_quantity
            )]


@router.post("/{cart_id}/add/{item_id}", status_code=HTTPStatus.OK)
async def add_cart_item(
        cart_id: int,
        item_id: int,
        quantity: Annotated[int, Query(ge=1)] = 1,
) -> CartResponse:
    item = item_repo.get_one(item_id)
    if not item:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{item_id} was not found",
        )

    cart = cart_repo.get_one(cart_id)
    if not cart:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /cart/{cart_id} was not found",
        )

    try:
        cart.add_item(item=item, quantity=quantity)
    except ValueError as e:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"{str(e)}"
        )

    cart_repo.save(cart)

    return CartResponse.from_entity(cart)
