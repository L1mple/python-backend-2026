from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse
from typing import Annotated

from shop_api.api.exceptions import HTTPItemNotFoundError, HTTPCartNotFoundError
from shop_api.core.deps import SessionDep
from shop_api.schemas.cart import CartListQuery, CartDB
from shop_api.services.cart import CartService
from shop_api.services.exceptions import CartNotFoundError, ItemNotFoundError

router = APIRouter(prefix="/cart", tags=["cart"])

@router.post(
    "",
)
async def create_new_cart(session: SessionDep):
    cart = await CartService(session).create_cart()
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"id": cart.id},
        headers={"Location": f"/cart/{cart.id}"},
    )


@router.get("", response_model=list[CartDB])
async def get_carts(
    session: SessionDep,
    query: Annotated[CartListQuery, Query()]
):
    cart_service = CartService(session)
    return await cart_service.get_carts(query)

@router.get(
    "/{cart_id}",
    response_model=CartDB,
)
async def get_cart_by_id(cart_id: int, session: SessionDep):
    cart_service = CartService(session)
    try:
        return await cart_service.get_cart_by_id(cart_id)
    except CartNotFoundError:
        raise HTTPCartNotFoundError()

@router.post(
    "/{cart_id}/add/{item_id}",
    response_model=CartDB,
)
async def add_item_cart(cart_id: int, item_id: int, session: SessionDep):
    cart_service = CartService(session)
    try:
        return await cart_service.add_item_to_cart(cart_id, item_id)
    except CartNotFoundError:
        raise HTTPCartNotFoundError()
    except ItemNotFoundError:
        raise HTTPItemNotFoundError()