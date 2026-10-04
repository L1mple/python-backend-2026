from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from shop_api import storage
from shop_api.contracts import CartCreatedResponse, CartItemResponse, CartResponse
from shop_api.storage import Cart

router = APIRouter(prefix="/cart", tags=["cart"])


def _cart_response(cart: Cart) -> CartResponse:
    items = []
    price = 0.0

    for item_id, quantity in cart.items.items():
        # Товары не удаляются из хранилища физически, поэтому item всегда найдётся
        item = storage.get_item(item_id)
        items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        # Удалённый товар купить нельзя, в сумму он не входит
        if not item.deleted:
            price += item.price * quantity

    return CartResponse(id=cart.id, items=items, price=price)


def _get_cart_or_404(cart_id: int) -> Cart:
    cart = storage.get_cart(cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")
    return cart


@router.post("", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> CartCreatedResponse:
    cart = storage.add_cart()
    response.headers["location"] = f"/cart/{cart.id}"
    return CartCreatedResponse(id=cart.id)


@router.get("/{cart_id}")
async def get_cart(cart_id: int) -> CartResponse:
    return _cart_response(_get_cart_or_404(cart_id))


@router.get("")
async def list_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[CartResponse]:
    result = []

    for cart in storage.all_carts():
        response = _cart_response(cart)
        quantity = sum(item.quantity for item in response.items)

        if min_price is not None and response.price < min_price:
            continue
        if max_price is not None and response.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(response)

    return result[offset : offset + limit]


@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    cart = _get_cart_or_404(cart_id)

    item = storage.get_item(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")

    storage.add_to_cart(cart, item)
    return _cart_response(cart)
