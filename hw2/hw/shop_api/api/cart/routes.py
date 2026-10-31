from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeInt, PositiveInt, PositiveFloat

from shop_api.store import cart as store
from shop_api.store import item as item_store

from shop_api.api.cart.contracts import (
    CreateCartResponse,
    CartItemResponse,
    CartResponse,
    CartListRequest
)

router = APIRouter(prefix="/cart")


@router.get("/")
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[PositiveFloat | None, Query()] = None,
    max_price: Annotated[PositiveFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None
    ) -> list[CartResponse]:
    return [CartResponse.from_entity(e) 
            for e in await store.get_many(offset, limit, min_price, max_price, min_quantity, max_quantity)]


@router.get(
    "/{id}",
    responses={
        HTTPStatus.OK: {
            "description": "Successfully returned requested cart",
        },
        HTTPStatus.NOT_FOUND: {
            "description": "Failed to return requested cart as one was not found",
        },
    },
)
async def get_cart_by_id(id: int) -> CartResponse:
    entity = await store.get_one(id)

    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /cart/{id} was not found",
        )

    return CartResponse.from_entity(entity)


@router.post(
    "/",
    status_code=HTTPStatus.CREATED,
)
async def post_cart(response: Response) -> CreateCartResponse:
    _id = await store.add()

    # as REST states one should provide uri to newly created resource in location header
    response.headers["location"] = f"/cart/{_id}"

    return CreateCartResponse(id=_id)


@router.post(
    "/{cart_id}/add/{item_id}",
    status_code=HTTPStatus.OK,
    responses={
        HTTPStatus.OK: {
            "description": "Successfully added item to cart",
        },
        HTTPStatus.NOT_FOUND: {
            "description": "Cart or item was not found",
        },
    },
)
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    new_item = await item_store.get_one(item_id)
    if new_item is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Cart {cart_id} was not found",
        )
    
    entity = await store.add_item(cart_id, new_item)
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Cart {cart_id} was not found",
        )
    
    return CartResponse.from_entity(entity)

