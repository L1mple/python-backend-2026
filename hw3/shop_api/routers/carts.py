from typing import Annotated

from fastapi import APIRouter, Query, Response

from shop_api import storage
from shop_api.schemas import CartCreated, CartResponse


router = APIRouter(prefix="/cart", tags=["carts"])


@router.post("", response_model=CartCreated, status_code=201)
def create_cart(response: Response):
    cart = storage.create_cart()
    response.headers["Location"] = f"/cart/{cart.id}"
    return CartCreated(id=cart.id)


@router.get("", response_model=list[CartResponse])
def list_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
):
    return storage.list_carts(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
    )


@router.get("/{cart_id}", response_model=CartResponse)
def get_cart(cart_id: int):
    cart = storage.get_cart(cart_id)
    return storage.build_cart_response(cart)


@router.post("/{cart_id}/add/{item_id}", status_code=200)
def add_item(cart_id: int, item_id: int):
    storage.add_item_to_cart(cart_id, item_id)
    return {"detail": "Item added"}
