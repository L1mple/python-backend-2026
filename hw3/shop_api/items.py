from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from shop_api import store
from shop_api.contracts import ItemRequest, ItemResponse, PatchItemRequest

router = APIRouter(prefix="/item", tags=["item"])


def _get_alive_item_or_404(item_id: int) -> store.ItemRecord:
    item = store.get_item(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return item


def _get_alive_item_or_304(item_id: int) -> store.ItemRecord:
    item = store.get_item(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} not modified")
    return item


@router.post("", status_code=HTTPStatus.CREATED)
async def post_item(body: ItemRequest, response: Response) -> ItemResponse:
    item = store.add_item(name=body.name, price=body.price)
    response.headers["location"] = f"/item/{item.id}"
    return ItemResponse.from_record(item)


@router.get("/{item_id}")
async def get_item(item_id: int) -> ItemResponse:
    return ItemResponse.from_record(_get_alive_item_or_404(item_id))


@router.get("")
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    items = [
        item
        for item in store.list_items()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return [ItemResponse.from_record(item) for item in items[offset : offset + limit]]


@router.put("/{item_id}")
async def put_item(item_id: int, body: ItemRequest) -> ItemResponse:
    item = _get_alive_item_or_304(item_id)
    item.name = body.name
    item.price = body.price
    return ItemResponse.from_record(item)


@router.patch("/{item_id}")
async def patch_item(item_id: int, body: PatchItemRequest) -> ItemResponse:
    item = _get_alive_item_or_304(item_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    return ItemResponse.from_record(item)


@router.delete("/{item_id}")
async def delete_item(item_id: int) -> Response:
    item = store.get_item(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    item.deleted = True
    return Response(status_code=HTTPStatus.OK)
