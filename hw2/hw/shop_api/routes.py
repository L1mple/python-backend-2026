from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from . import store
from .contracts import (
    CartCreateResponse,
    CartItemResponse,
    CartResponse,
    ItemRequest,
    ItemResponse,
    PatchItemRequest,
)
from .models import Cart, Item


router = APIRouter()


def item_to_response(item: Item) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        name=item.name,
        price=item.price,
        deleted=item.deleted,
    )


def cart_to_response(cart: Cart) -> CartResponse:
    cart_items = []
    price = 0.0

    for item_id, quantity in cart.items.items():
        item = store.get_item(item_id)

        if item is None:
            continue

        cart_items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )

        price += item.price * quantity

    return CartResponse(
        id=cart.id,
        items=cart_items,
        price=price,
    )


@router.post(
    "/item",
    status_code=HTTPStatus.CREATED,
)
async def post_item(
    info: ItemRequest,
    response: Response,
) -> ItemResponse:
    item = store.add_item(info.name, info.price)

    response.headers["location"] = f"/item/{item.id}"

    return item_to_response(item)


@router.get("/item/{item_id}")
async def get_item(item_id: int) -> ItemResponse:
    item = store.get_item(item_id)

    if item is None or item.deleted:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /item/{item_id} was not found",
        )

    return item_to_response(item)


@router.get("/item")
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    result = []

    for item in store.get_all_items():
        if item.deleted and not show_deleted:
            continue

        if min_price is not None and item.price < min_price:
            continue

        if max_price is not None and item.price > max_price:
            continue

        result.append(item_to_response(item))

    return result[offset : offset + limit]


@router.put("/item/{item_id}")
async def put_item(
    item_id: int,
    info: ItemRequest,
) -> ItemResponse:
    item = store.update_item(
        item_id,
        info.name,
        info.price,
    )

    if item is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{item_id} was not found",
        )

    return item_to_response(item)


@router.patch("/item/{item_id}")
async def patch_item(
    item_id: int,
    info: PatchItemRequest,
) -> ItemResponse:
    item = store.patch_item(
        item_id,
        info.name,
        info.price,
    )

    if item is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{item_id} was not found",
        )

    return item_to_response(item)


@router.delete("/item/{item_id}")
async def delete_item(item_id: int) -> Response:
    store.delete_item(item_id)

    return Response(status_code=HTTPStatus.OK)


@router.post(
    "/cart",
    status_code=HTTPStatus.CREATED,
)
async def post_cart(response: Response) -> CartCreateResponse:
    cart = store.add_cart()

    response.headers["location"] = f"/cart/{cart.id}"

    return CartCreateResponse(id=cart.id)


@router.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> CartResponse:
    cart = store.get_cart(cart_id)

    if cart is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /cart/{cart_id} was not found",
        )

    return cart_to_response(cart)


@router.get("/cart")
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    result = []

    for cart in store.get_all_carts():
        cart_response = cart_to_response(cart)
        quantity = sum(item.quantity for item in cart_response.items)

        if min_price is not None and cart_response.price < min_price:
            continue

        if max_price is not None and cart_response.price > max_price:
            continue

        if min_quantity is not None and quantity < min_quantity:
            continue

        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart_response)

    return result[offset : offset + limit]


@router.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(
    cart_id: int,
    item_id: int,
) -> Response:
    cart = store.get_cart(cart_id)
    item = store.get_item(item_id)

    if cart is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /cart/{cart_id} was not found",
        )

    if item is None or item.deleted:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /item/{item_id} was not found",
        )

    store.add_item_to_cart(cart_id, item_id)

    return Response(status_code=HTTPStatus.OK)