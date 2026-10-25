from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from .models import Item, ItemData, ItemFilters, ItemPatch, ItemReplacement
from .store import Store, StoreDependency

router = APIRouter(prefix="/item")


def require_item(
    item_id: int, store: Store, include_deleted: bool = False, lock: bool = False
) -> Item:
    item = store.get_item(item_id, lock=lock)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


@router.post("", status_code=HTTPStatus.CREATED)
def create_item(data: ItemData, response: Response, store: StoreDependency) -> Item:
    item = store.create_item(data)
    response.headers["Location"] = f"/item/{item.id}"
    return item


@router.get("")
def list_items(
    filters: Annotated[ItemFilters, Query()], store: StoreDependency
) -> list[Item]:
    return store.list_items(filters)


@router.get("/{item_id}")
def get_item(item_id: int, store: StoreDependency) -> Item:
    return require_item(item_id, store)


@router.put("/{item_id}")
def replace_item(item_id: int, data: ItemReplacement, store: StoreDependency) -> Item:
    require_item(item_id, store, include_deleted=True, lock=True)
    return store.replace_item(item_id, data)


@router.patch("/{item_id}", response_model=Item)
def patch_item(
    item_id: int, data: ItemPatch, store: StoreDependency
) -> Item | Response:
    item = require_item(item_id, store, include_deleted=True, lock=True)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    return store.patch_item(item_id, data)


@router.delete("/{item_id}")
def delete_item(item_id: int, store: StoreDependency) -> Response:
    require_item(item_id, store, include_deleted=True, lock=True)
    store.delete_item(item_id)
    return Response(status_code=HTTPStatus.OK)
