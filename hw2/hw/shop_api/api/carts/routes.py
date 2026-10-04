from http import HTTPStatus
from typing import Annotated
from fastapi import APIRouter, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt
from .contracts import CartResponse
from ...store import queries


router = APIRouter(prefix="/cart")


@router.post("", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response) -> dict[str, int]:
    cart = queries.add_cart()
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@router.get("/{id}")
async def get_cart(id: int) -> CartResponse:
    cart = queries.get_cart(id)
    return CartResponse.from_entity(cart)


@router.get("")
async def get_carts(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    carts = queries.get_carts(offset, limit, min_price, max_price, min_quantity, max_quantity)
    return [CartResponse.from_entity(cart) for cart in carts]


@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    cart = queries.add_item_to_cart(cart_id, item_id)
    return CartResponse.from_entity(cart)
