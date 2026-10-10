from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from shop_api.cart.contracts import CartResponse
from store.cart import queries

router = APIRouter()


@router.post("", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> CartResponse:
    entity = queries.add()
    response.headers["location"] = f"/cart/{entity.id}"
    return CartResponse.from_entity(entity)


@router.get("")
async def get_cart_list(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[CartResponse]:
    entities = queries.get_many(
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
        HTTPStatus.NOT_FOUND: {
            "description": "Failed to return requested cart as one was not found"
        },
    },
)
async def get_cart_by_id(id: int) -> CartResponse:
    entity = queries.get(id)
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /cart/{id} was not found",
        )
    return CartResponse.from_entity(entity)


@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    entity = queries.add_item(cart_id, item_id)
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /cart/{cart_id} was not found",
        )
    return CartResponse.from_entity(entity)
