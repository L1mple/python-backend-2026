from http import HTTPStatus
from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt
from shop_api import store

from .contracts import CartItemResponse, CartResponse

router = APIRouter(prefix="/cart", tags=["cart"])


def _build_cart_response(cart_id: int) -> CartResponse:
    cart = store.get_cart(cart_id)

    if cart is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /cart/{cart_id} was not found",
        )

    items: list[CartItemResponse] = []
    total_price = 0.0

    for item_id, quantity in cart.items():
        item = store.get_item(item_id)

        if item is None:
            continue

        items.append(
            CartItemResponse(
                id=item_id,
                name=item.info.name,
                quantity=quantity,
                available=not item.info.deleted,
            )
        )
        total_price += item.info.price * quantity

    return CartResponse(id=cart_id, items=items, price=total_price)


@router.post("/", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response) -> dict[str, int]:
    cart_id = store.add_cart()
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@router.get("/{id}")
async def get_cart_by_id(id: int) -> CartResponse:
    return _build_cart_response(id)


@router.get("/")
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    carts = store.get_carts()
    result: list[CartResponse] = []

    for cart_id, _ in carts:
        cart_response = _build_cart_response(cart_id)

        total_quantity = sum(item.quantity for item in cart_response.items)

        if min_price is not None and cart_response.price < min_price:
            continue
        if max_price is not None and cart_response.price > max_price:
            continue
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue

        result.append(cart_response)

    return result[offset : offset + limit]


@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    ok = store.add_item_to_cart(cart_id, item_id)

    if not ok:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Cart {cart_id} or item {item_id} was not found",
        )

    return _build_cart_response(cart_id)
