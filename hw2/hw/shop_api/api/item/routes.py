from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from shop_api import store

from .contracts import ItemRequest, ItemResponse, PatchItemRequest

router = APIRouter(prefix='/item')


@router.post('', status_code=HTTPStatus.CREATED)
async def create_item(body: ItemRequest) -> ItemResponse:
    entity = store.add_item(body.as_item_info())
    return ItemResponse.from_entity(entity)


@router.get('')
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    entities = store.get_items(offset, limit, min_price, max_price, show_deleted)
    return [ItemResponse.from_entity(e) for e in entities]


@router.get('/{item_id}')
async def get_item(item_id: int) -> ItemResponse:
    entity = store.get_item(item_id)
    if entity is None or entity.info.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, 'item not found')
    return ItemResponse.from_entity(entity)


@router.put('/{item_id}')
async def put_item(item_id: int, body: ItemRequest) -> ItemResponse:
    entity = store.update_item(item_id, body.name, body.price)
    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, 'item not found')
    return ItemResponse.from_entity(entity)


@router.patch('/{item_id}', response_model=None)
async def patch_item(item_id: int, body: PatchItemRequest):
    entity = store.patch_item(item_id, body.as_patch_item_info())
    if entity is None:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    return ItemResponse.from_entity(entity)


@router.delete('/{item_id}')
async def delete_item(item_id: int) -> Response:
    store.delete_item(item_id)
    return Response(status_code=HTTPStatus.OK)
