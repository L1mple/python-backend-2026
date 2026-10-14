from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from shop_api.item.contracts import (
    ItemRequest,
    ItemResponse,
    PatchItemRequest,
    PutItemRequest,
)
from store.item import queries

router = APIRouter()


@router.post("", status_code=HTTPStatus.CREATED)
async def create_item(item: ItemRequest) -> ItemResponse:
    entity = queries.add(name=item.name, price=item.price)
    return ItemResponse.from_entity(entity)


@router.get("")
async def get_item_list(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[ItemResponse]:
    entities = queries.get_many(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )
    return [ItemResponse.from_entity(entity) for entity in entities]


@router.get("/{id}")
async def get_item_by_id(id: int) -> ItemResponse:
    entity = queries.get(id)
    if entity is None or entity.deleted:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{id} was not found",
        )
    return ItemResponse.from_entity(entity)


@router.put("/{id}")
async def replace_item(id: int, item: PutItemRequest) -> ItemResponse:
    entity = queries.replace(id, name=item.name, price=item.price)
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{id} was not found",
        )
    return ItemResponse.from_entity(entity)


@router.patch("/{id}")
async def update_item(id: int, item: PatchItemRequest) -> ItemResponse:
    entity = queries.get(id)
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{id} was not found",
        )
    if entity.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    updated = queries.patch(id, name=item.name, price=item.price)
    return ItemResponse.from_entity(updated)


@router.delete("/{id}")
async def delete_item(id: int) -> Response:
    queries.delete(id)
    return Response(status_code=HTTPStatus.OK)
