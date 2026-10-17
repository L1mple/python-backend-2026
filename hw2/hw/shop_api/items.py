from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from .models import Item, ItemData, ItemFilters, ItemPatch, ItemReplacement
from .store import store

router = APIRouter(prefix="/item")


def require_item(item_id: int, include_deleted: bool = False) -> Item:
    item = store.get_item(item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


@router.post("", status_code=HTTPStatus.CREATED)
async def create_item(data: ItemData, response: Response) -> Item:
    item = store.create_item(data)
    response.headers["Location"] = f"/item/{item.id}"
    return item


@router.get("")
async def list_items(filters: Annotated[ItemFilters, Query()]) -> list[Item]:
    return store.list_items(filters)


@router.get("/{item_id}")
async def get_item(item_id: int) -> Item:
    return require_item(item_id)


@router.put("/{item_id}")
async def replace_item(item_id: int, data: ItemReplacement) -> Item:
    require_item(item_id, include_deleted=True)
    return store.replace_item(item_id, data)


@router.patch("/{item_id}", response_model=Item)
async def patch_item(item_id: int, data: ItemPatch) -> Item | Response:
    item = require_item(item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    return store.patch_item(item_id, data)


@router.delete("/{item_id}")
async def delete_item(item_id: int) -> Response:
    require_item(item_id, include_deleted=True)
    store.delete_item(item_id)
    return Response(status_code=HTTPStatus.OK)
