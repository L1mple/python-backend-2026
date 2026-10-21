from decimal import Decimal
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Response, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shop_api.cart.contracts import CartResponse

import store.db.cart as cart_repo
import store.db.item as item_repo

from store.db.db import get_async_session

router = APIRouter()


@router.post("", status_code=HTTPStatus.CREATED)
async def add_cart(
        response: Response,
        session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CartResponse:
    entity = await cart_repo.add(session)

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
async def get_cart(
        cart_id: int,
        session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CartResponse:
    entity = await cart_repo.get_one(session, cart_id)
    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /cart/{cart_id} was not found",
        )
    return CartResponse.from_entity(entity)


@router.get("", status_code=HTTPStatus.OK)
async def get_cart_list(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1)] = 10,
        min_price: Annotated[Decimal | None, Query(ge=0)] = None,
        max_price: Annotated[Decimal | None, Query(ge=0)] = None,
        min_quantity: Annotated[int | None, Query(ge=0)] = None,
        max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[CartResponse]:
    entities = await cart_repo.get_many(
        session,
        offset,
        limit,
        min_price,
        max_price,
        min_quantity,
        max_quantity,
    )
    return [CartResponse.from_entity(e) for e in entities]


@router.post("/{cart_id}/add/{item_id}", status_code=HTTPStatus.OK)
async def add_cart_item(
        cart_id: int,
        item_id: int,
        session: Annotated[AsyncSession, Depends(get_async_session)],
        quantity: Annotated[int, Query(ge=1)] = 1,
) -> CartResponse:
    item = await item_repo.get_one(session, item_id)
    if not item:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{item_id} was not found",
        )

    cart = await cart_repo.get_one(session, cart_id)
    if not cart:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /cart/{cart_id} was not found",
        )

    cart = await cart_repo.add_item(session, cart_id, item_id, quantity)

    return CartResponse.from_entity(cart)
