from __future__ import annotations

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from shop_api import store
from shop_api.contracts import ItemCreate, ItemPatch, ItemResponse, ItemUpdate

router = APIRouter(prefix="/item", tags=["item"])


@router.post("", status_code=HTTPStatus.CREATED)
def create_item(payload: ItemCreate) -> ItemResponse:
    item = store.create_item(payload.name, payload.price)
    return ItemResponse(**item)


@router.get("")
def list_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[ItemResponse]:
    found = store.list_items(offset, limit, min_price, max_price, show_deleted)
    return [ItemResponse(**item) for item in found]


@router.get("/{item_id}")
def get_item(item_id: int) -> ItemResponse:
    item = store.get_item(item_id)
    if item is None or item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return ItemResponse(**item)


@router.put("/{item_id}")
def replace_item(item_id: int, payload: ItemUpdate) -> ItemResponse:
    item = store.get_item(item_id)
    if item is None or item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} not found")
    updated = store.replace_item(item_id, payload.name, payload.price)
    return ItemResponse(**updated)


@router.patch("/{item_id}")
def patch_item(item_id: int, payload: ItemPatch):
    item = store.get_item(item_id)
    if item is None or item["deleted"]:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    updated = store.patch_item(item_id, payload.name, payload.price)
    return ItemResponse(**updated)


@router.delete("/{item_id}")
def delete_item(item_id: int) -> ItemResponse:
    item = store.get_item(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    store.mark_item_deleted(item_id)
    return ItemResponse(**item)
