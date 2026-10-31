from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from . import storage

from .contracts import (
    CartIdResponse,
    CartResponse,
    ItemRequest,
    ItemResponse,
    PatchItemRequest,
)

router = APIRouter()


@router.post("/cart", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response) -> CartIdResponse:
    entity = storage.add_cart()
    response.headers["location"] = f"/cart/{entity.id}"
    return CartIdResponse(id=entity.id)


@router.get("/cart/{id}")
async def get_cart_by_id(id: int) -> CartResponse:
    entity = storage.get_cart(id)
    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Requested resource /cart/{id} was not found")
    return CartResponse.from_entity(entity)


@router.get("/cart")
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    entities = storage.get_carts(offset, limit, min_price, max_price, min_quantity, max_quantity)
    return [CartResponse.from_entity(entity) for entity in entities]


@router.post("/cart/{cart_id}/add/{item_id}")
async def post_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    entity = storage.add_item_to_cart(cart_id, item_id)
    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Requested cart or item was not found")
    return CartResponse.from_entity(entity)


@router.post("/item", status_code=HTTPStatus.CREATED)
async def post_item(info: ItemRequest, response: Response) -> ItemResponse:
    entity = storage.add_item(info.name, info.price)
    response.headers["location"] = f"/item/{entity.id}"
    return ItemResponse.from_entity(entity)


@router.get("/item/{id}")
async def get_item_by_id(id: int) -> ItemResponse:
    entity = storage.get_item(id)
    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Requested resource /item/{id} was not found")
    return ItemResponse.from_entity(entity)


@router.get("/item")
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    entities = storage.get_items(offset, limit, min_price, max_price, show_deleted)
    return [ItemResponse.from_entity(entity) for entity in entities]


@router.put("/item/{id}")
async def put_item(id: int, info: ItemRequest) -> ItemResponse:
    entity = storage.update_item(id, info.name, info.price)
    if entity is None:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Requested resource /item/{id} was not found")
    return ItemResponse.from_entity(entity)


@router.patch("/item/{id}")
async def patch_item(id: int, info: PatchItemRequest) -> ItemResponse:
    entity = storage.patch_item(id, name=info.name, price=info.price)
    if entity is None:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Requested resource /item/{id} was not found")
    return ItemResponse.from_entity(entity)


@router.delete("/item/{id}")
async def delete_item(id: int) -> Response:
    storage.delete_item(id)
    return Response("")
