from __future__ import annotations

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from shop_api import store
from shop_api.contracts import (
    CartCreatedResponse,
    CartItemResponse,
    CartResponse,
)

router = APIRouter(prefix="/cart", tags=["cart"])


def _build_cart_response(cart_id: int) -> CartResponse:
    contents = store.get_cart_contents(cart_id)
    assert contents is not None

    cart_items: list[CartItemResponse] = []
    total = 0.0

    for item_id, quantity in contents.items():
        item = store.get_item(item_id)
        assert item is not None

        cart_items.append(
            CartItemResponse(
                id=item_id,
                name=item["name"],
                quantity=quantity,
                available=not item["deleted"],
            )
        )
        total += item["price"] * quantity

    return CartResponse(id=cart_id, items=cart_items, price=total)


@router.post("", status_code=HTTPStatus.CREATED)
def create_cart(response: Response) -> CartCreatedResponse:
    cart_id = store.create_cart()
    response.headers["location"] = f"/cart/{cart_id}"
    return CartCreatedResponse(id=cart_id)


@router.get("")
def list_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[CartResponse]:
    cart_ids = store.list_carts(
        offset, limit, min_price, max_price, min_quantity, max_quantity
    )
    return [_build_cart_response(cid) for cid in cart_ids]


@router.get("/{cart_id}")
def get_cart(cart_id: int) -> CartResponse:
    if store.get_cart_contents(cart_id) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")
    return _build_cart_response(cart_id)


@router.post("/{cart_id}/add/{item_id}")
def add_item(cart_id: int, item_id: int) -> CartResponse:
    if store.get_cart_contents(cart_id) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")

    item = store.get_item(item_id)
    if item is None or item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")

    store.add_item_to_cart(cart_id, item_id)
    return _build_cart_response(cart_id)
