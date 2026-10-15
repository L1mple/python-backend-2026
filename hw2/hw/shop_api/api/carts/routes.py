from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from .contracts import CartResponse
from ...store import queries
from ...store.database import SessionDependency


router = APIRouter(prefix="/cart")


@router.post("", status_code=HTTPStatus.CREATED)
async def post_cart(session: SessionDependency, response: Response) -> dict[str, int]:
    cart = await queries.add_cart(session)
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@router.get("/{id}")
async def get_cart(session: SessionDependency, id: int) -> CartResponse:
    cart_with_price = await queries.get_cart(session, id)

    if cart_with_price is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return CartResponse.from_entity(cart_with_price)


@router.get("")
async def get_carts(
    session: SessionDependency,
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    carts = await queries.get_carts(
        session, offset, limit, min_price, max_price, min_quantity, max_quantity
    )
    return [CartResponse.from_entity(cart) for cart in carts]


@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(
    session: SessionDependency,
    cart_id: int,
    item_id: int,
) -> CartResponse:
    cart_with_price = await queries.add_item_to_cart(session, cart_id, item_id)

    if cart_with_price is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return CartResponse.from_entity(cart_with_price)
