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


@router.post("", status_code=HTTPStatus.CREATED)
def post_item(body: ItemRequest, response: Response) -> ItemResponse:
    item = store.add_item(name=body.name, price=body.price)
    response.headers["location"] = f"/item/{item.id}"
    return ItemResponse.from_record(item)


@router.get("/{item_id}")
def get_item(item_id: int) -> ItemResponse:
    return ItemResponse.from_record(_get_alive_item_or_404(item_id))


@router.get("")
def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    items = store.list_items(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )
    return [ItemResponse.from_record(item) for item in items]


@router.put("/{item_id}")
def put_item(item_id: int, body: ItemRequest) -> ItemResponse:
    item = store.update_item(item_id, name=body.name, price=body.price)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} not modified")
    return ItemResponse.from_record(item)


@router.patch("/{item_id}")
def patch_item(item_id: int, body: PatchItemRequest) -> ItemResponse:
    item = store.update_item(item_id, **body.model_dump(exclude_unset=True))
    if item is None:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} not modified")
    return ItemResponse.from_record(item)


@router.delete("/{item_id}")
def delete_item(item_id: int) -> Response:
    if not store.delete_item(item_id):
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return Response(status_code=HTTPStatus.OK)
