from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import NonNegativeInt, PositiveFloat, PositiveInt
from sqlalchemy.orm import Session

from store import queries
from store import ItemInsertionResult

from .contracts import (
    CartCreatedResponse,
    CartResponse,
)
from .session import get_session

router = APIRouter(prefix="/cart", tags=["cart"])


def _make_item_lookup(session: Session):
    def lookup(item_id: int):
        entity = queries.get_item(session, item_id)
        return entity.info
    return lookup


@router.get("")
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[PositiveFloat | None, Query()] = None,
    max_price: Annotated[PositiveFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    session: Session = Depends(get_session),
) -> list[CartResponse]:
    item_lookup = _make_item_lookup(session)
    return [
        CartResponse.from_entity(e, item_lookup)
        for e in queries.get_cart_multiple(
            session,
            offset=offset,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
        )
    ]


@router.get(
    "/{id}",
    responses={
        HTTPStatus.OK: {"description": "Successfully returned requested cart"},
        HTTPStatus.NOT_FOUND: {"description": "Cart was not found"},
    },
)
async def get_cart_by_id(
    id: int,
    session: Session = Depends(get_session),
) -> CartResponse:
    entity = queries.get_cart(session, id)
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /cart/{id} was not found",
        )
    return CartResponse.from_entity(entity, _make_item_lookup(session))


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
)
async def post_cart(
    response: Response,
    session: Session = Depends(get_session),
) -> CartCreatedResponse:
    entity = queries.add_cart(session)
    response.headers["location"] = f"/cart/{entity.id}"
    return CartCreatedResponse(id=entity.id)


@router.post(
    "/{cart_id}/add/{item_id}",
    responses={
        HTTPStatus.OK: {"description": "Item added to cart"},
        HTTPStatus.NOT_FOUND: {"description": "Cart or item was not found"},
    },
)
async def add_item_to_cart(
    cart_id: int,
    item_id: int,
    session: Session = Depends(get_session),
) -> CartResponse:
    result = queries.insert_item_to_cart(session, cart_id, item_id)
    if result == ItemInsertionResult.CART_NOT_FOUND:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart /cart/{cart_id} was not found")
    if result == ItemInsertionResult.ITEM_NOT_FOUND:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item /item/{item_id} was not found")

    entity = queries.get_cart(session, cart_id)
    return CartResponse.from_entity(entity, _make_item_lookup(session))