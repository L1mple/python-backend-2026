from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from .items import require_item
from .models import Cart, CartCreated, CartFilters
from .store import store

router = APIRouter(prefix="/cart")


def require_cart(cart_id: int) -> Cart:
    cart = store.get_cart(cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return cart


@router.post("", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> CartCreated:
    cart_id = store.create_cart()
    response.headers["Location"] = f"/cart/{cart_id}"
    return CartCreated(id=cart_id)


@router.get("")
async def list_carts(filters: Annotated[CartFilters, Query()]) -> list[Cart]:
    return store.list_carts(filters)


@router.get("/{cart_id}")
async def get_cart(cart_id: int) -> Cart:
    return require_cart(cart_id)


@router.post("/{cart_id}/add/{item_id}")
async def add_item(cart_id: int, item_id: int) -> Cart:
    require_cart(cart_id)
    require_item(item_id)
    store.add_item(cart_id, item_id)
    return require_cart(cart_id)
