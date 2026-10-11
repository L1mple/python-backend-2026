from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Query, Response

from shop_api import store
from shop_api.contracts import CartItemResponse, CartResponse

router = APIRouter(prefix="/cart")


def _to_response(cart: store.CartInfo) -> CartResponse:
    items = []
    for item_id, quantity in cart.items.items():
        item = store.get_item(item_id)
        if item is None:
            continue
        items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
    return CartResponse(id=cart.id, items=items, price=store.cart_price(cart))


@router.post("", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response) -> dict[str, int]:
    cart = store.add_cart()
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@router.get("/{id}")
async def get_cart_by_id(id: int) -> CartResponse:
    cart = store.get_cart(id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {id} not found")
    return _to_response(cart)


@router.get("")
async def get_cart_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
) -> list[CartResponse]:
    carts = store.list_carts(offset, limit, min_price, max_price, min_quantity, max_quantity)
    return [_to_response(cart) for cart in carts]


@router.post("/{cart_id}/add/{item_id}")
async def post_add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    cart = store.add_item_to_cart(cart_id, item_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart or item not found")
    return _to_response(cart)