from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from shop_api import store
from shop_api.contracts import CartIdResponse, CartResponse

router = APIRouter(prefix="/cart", tags=["cart"])


def _get_cart_or_404(cart_id: int) -> store.CartRecord:
    cart = store.get_cart(cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")
    return cart


@router.post("", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response) -> CartIdResponse:
    cart = store.add_cart()
    response.headers["location"] = f"/cart/{cart.id}"
    return CartIdResponse(id=cart.id)


@router.get("/{cart_id}")
async def get_cart(cart_id: int) -> CartResponse:
    return CartResponse.from_record(_get_cart_or_404(cart_id))


@router.get("")
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    carts = [CartResponse.from_record(cart) for cart in store.list_carts()]
    carts = [
        cart
        for cart in carts
        if (min_price is None or cart.price >= min_price)
        and (max_price is None or cart.price <= max_price)
        and (min_quantity is None or cart.quantity >= min_quantity)
        and (max_quantity is None or cart.quantity <= max_quantity)
    ]
    return carts[offset : offset + limit]


@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    cart = _get_cart_or_404(cart_id)
    item = store.get_item(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")

    cart.items[item_id] = cart.items.get(item_id, 0) + 1
    return CartResponse.from_record(cart)
