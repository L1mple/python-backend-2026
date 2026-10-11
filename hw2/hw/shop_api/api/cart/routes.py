from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from shop_api import store

from .contracts import CartResponse

router = APIRouter(prefix='/cart')


@router.post('', status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> dict[str, int]:
    entity = store.add_cart()
    response.headers['location'] = f'/cart/{entity.id}'
    return {'id': entity.id}


@router.get('')
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    result = []

    for entity in store.get_carts():
        cart = CartResponse.from_entity(entity)
        quantity = sum(entity.items.values())

        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset:offset + limit]


@router.get('/{cart_id}')
async def get_cart(cart_id: int) -> CartResponse:
    entity = store.get_cart(cart_id)
    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, 'cart not found')
    return CartResponse.from_entity(entity)


@router.post('/{cart_id}/add/{item_id}')
async def add_to_cart(cart_id: int, item_id: int) -> CartResponse:
    entity = store.add_to_cart(cart_id, item_id)
    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, 'cart or item not found')
    return CartResponse.from_entity(entity)
