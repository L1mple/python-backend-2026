from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from . import store
from .contracts import CartResponse, ItemRequest, ItemResponse, PatchItemRequest


router = APIRouter()


@router.post("/cart", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> dict[str, int]:
    cart = store.add_cart()
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@router.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> CartResponse:
    cart = store.get_cart(cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Корзина не найдена")
    return CartResponse.from_entity(cart)


@router.get("/cart")
async def get_carts(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    carts = store.get_carts(
        offset,
        limit,
        min_price,
        max_price,
        min_quantity,
        max_quantity,
    )
    return [CartResponse.from_entity(cart) for cart in carts]


@router.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    cart = store.add_item_to_cart(cart_id, item_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Корзина или товар не найдены")
    return CartResponse.from_entity(cart)


@router.post("/item", status_code=HTTPStatus.CREATED)
async def create_item(info: ItemRequest, response: Response) -> ItemResponse:
    item = store.add_item(info.as_item_info())
    response.headers["location"] = f"/item/{item.id}"
    return ItemResponse.from_entity(item)


@router.get("/item/{item_id}")
async def get_item(item_id: int) -> ItemResponse:
    item = store.get_item(item_id)
    if item is None or item.info.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Товар не найден")
    return ItemResponse.from_entity(item)


@router.get("/item")
async def get_items(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    result = store.get_items(offset, limit, min_price, max_price, show_deleted)
    return [ItemResponse.from_entity(item) for item in result]


@router.put("/item/{item_id}")
async def replace_item(item_id: int, info: ItemRequest) -> ItemResponse:
    item = store.update_item(item_id, info.as_item_info())
    if item is None:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, "Товар не был изменён")
    return ItemResponse.from_entity(item)


@router.patch("/item/{item_id}")
async def update_item(item_id: int, info: PatchItemRequest) -> ItemResponse:
    item = store.patch_item(item_id, info.as_patch_item_info())
    if item is None:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, "Товар не был изменён")
    return ItemResponse.from_entity(item)


@router.delete("/item/{item_id}")
async def delete_item(item_id: int) -> ItemResponse:
    item = store.delete_item(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Товар не найден")
    return ItemResponse.from_entity(item)
