from http import HTTPStatus
from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt
from .contracts import ItemPatchRequest, ItemRequest, ItemResponse
from ...store import queries


router = APIRouter(prefix="/item")


@router.post("", status_code=HTTPStatus.CREATED)
async def post_item(body: ItemRequest) -> ItemResponse:
    item = queries.add_item(body.name, body.price)
    return ItemResponse.from_entity(item)


@router.get("/{id}")
async def get_item(id: int) -> ItemResponse:
    item = queries.get_item(id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    return ItemResponse.from_entity(item)


@router.get("")
async def get_items(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: bool = False,
) -> list[ItemResponse]:
    items = queries.get_items(offset, limit, min_price, max_price, show_deleted)
    return [ItemResponse.from_entity(item) for item in items]


@router.put("/{id}")
async def put_item(id: int, body: ItemRequest) -> ItemResponse:
    item = queries.update_item(id, body.name, body.price)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    return ItemResponse.from_entity(item)


@router.patch("/{id}")
async def patch_item(id: int, body: ItemPatchRequest) -> ItemResponse:
    item = queries.get_item(id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)
    return ItemResponse.from_entity(queries.patch_item(id, body.name, body.price))


@router.delete("/{id}")
async def delete_item(id: int) -> Response:
    queries.delete_item(id)
    return Response()
