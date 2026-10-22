from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from shop_api import store

from .contracts import CartResponse

router = APIRouter(prefix="/cart", tags=["cart"])


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    responses={
        HTTPStatus.CREATED: {"description": "Successfully created new cart"},
    },
)
async def post_cart(response: Response) -> CartResponse:
    entity = store.add_cart()

    response.headers["location"] = f"/cart/{entity.id}"

    return CartResponse.from_entity(entity)


@router.get(
    "",
    responses={
        HTTPStatus.OK: {"description": "Successfully returned list of carts"},
    },
)
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    entities = store.get_many_carts(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
    )

    return [CartResponse.from_entity(entity) for entity in entities]


@router.get(
    "/{id}",
    responses={
        HTTPStatus.OK: {"description": "Successfully returned requested cart"},
        HTTPStatus.NOT_FOUND: {"description": "Requested cart was not found"},
    },
)
async def get_cart_by_id(id: int) -> CartResponse:
    entity = store.get_cart(id)

    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /cart/{id} was not found",
        )

    return CartResponse.from_entity(entity)


@router.post(
    "/{cart_id}/add/{item_id}",
    responses={
        HTTPStatus.OK: {"description": "Successfully added item to cart"},
        HTTPStatus.NOT_FOUND: {
            "description": "Either requested cart or item was not found",
        },
    },
)
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    entity = store.add_item_to_cart(cart_id, item_id)

    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /cart/{cart_id}/add/{item_id} was not found",
        )

    return CartResponse.from_entity(entity)
