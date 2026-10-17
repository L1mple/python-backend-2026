from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from .items import require_item
from .models import Cart, CartCreated, CartFilters
from .store import Store, StoreDependency

router = APIRouter(prefix="/cart")


def require_cart(cart_id: int, store: Store, lock: bool = False) -> Cart:
    cart = store.get_cart(cart_id, lock=lock)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return cart


@router.post("", status_code=HTTPStatus.CREATED)
def create_cart(response: Response, store: StoreDependency) -> CartCreated:
    cart_id = store.create_cart()
    response.headers["Location"] = f"/cart/{cart_id}"
    return CartCreated(id=cart_id)


@router.get("")
def list_carts(
    filters: Annotated[CartFilters, Query()], store: StoreDependency
) -> list[Cart]:
    return store.list_carts(filters)


@router.get("/{cart_id}")
def get_cart(cart_id: int, store: StoreDependency) -> Cart:
    return require_cart(cart_id, store)


@router.post("/{cart_id}/add/{item_id}")
def add_item(cart_id: int, item_id: int, store: StoreDependency) -> Cart:
    require_cart(cart_id, store, lock=True)
    require_item(item_id, store, lock=True)
    store.add_item(cart_id, item_id)
    return require_cart(cart_id, store)
