from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from shop_api import storage
from shop_api.contracts import ItemPatchRequest, ItemRequest, ItemResponse
from shop_api.storage import Item

router = APIRouter(prefix="/item", tags=["item"])


def _get_item_or_404(item_id: int) -> Item:
    item = storage.get_item(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return item


def _get_editable_item(item_id: int) -> Item:
    item = _get_item_or_404(item_id)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)
    return item


@router.post("", status_code=HTTPStatus.CREATED)
async def create_item(body: ItemRequest, response: Response) -> ItemResponse:
    item = storage.add_item(body.name, body.price)
    response.headers["location"] = f"/item/{item.id}"
    return ItemResponse.from_item(item)


@router.get("/{item_id}")
async def get_item(item_id: int) -> ItemResponse:
    item = _get_item_or_404(item_id)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return ItemResponse.from_item(item)


@router.get("")
async def list_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[ItemResponse]:
    items = [
        item
        for item in storage.all_items()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return [ItemResponse.from_item(item) for item in items[offset : offset + limit]]


@router.put("/{item_id}")
async def replace_item(item_id: int, body: ItemRequest) -> ItemResponse:
    item = _get_editable_item(item_id)
    item.name = body.name
    item.price = body.price
    return ItemResponse.from_item(item)


@router.patch("/{item_id}")
async def update_item(item_id: int, body: ItemPatchRequest) -> ItemResponse:
    item = _get_editable_item(item_id)
    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    return ItemResponse.from_item(item)


@router.delete("/{item_id}")
async def delete_item(item_id: int) -> ItemResponse:
    # Повторное удаление тоже отвечает 200: результат тот же
    item = _get_item_or_404(item_id)
    item.deleted = True
    return ItemResponse.from_item(item)
