from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from ...store import (
    create_item,
    delete_item,
    get_item,
    get_items,
    patch_item,
    update_item,
)
from .contracts import ItemRequest, ItemResponse, PatchItemRequest

router = APIRouter(prefix="/item")


@router.post("/", status_code=HTTPStatus.CREATED)
async def post_item(info: ItemRequest, response: Response) -> ItemResponse:
    entity = create_item(info.as_item_info())
    response.headers["location"] = f"/item/{entity.id}"
    return ItemResponse.from_entity(entity)


@router.get("/", response_model=list[ItemResponse])
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    items = get_items(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )
    return [ItemResponse.from_entity(e) for e in items]


@router.get("/{item_id}")
async def get_item_by_id(item_id: int) -> ItemResponse:
    entity = get_item(item_id)
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Item {item_id} not found",
        )
    return ItemResponse.from_entity(entity)


@router.put("/{item_id}")
async def put_item(item_id: int, info: ItemRequest) -> ItemResponse:
    entity = update_item(item_id, info.as_item_info())
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Item {item_id} not found",
        )
    return ItemResponse.from_entity(entity)


@router.patch("/{item_id}")
async def patch_item_by_id(
    item_id: int,
    info: PatchItemRequest,
) -> ItemResponse:
    entity = patch_item(item_id, info.as_patch_item_info())
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Item {item_id} not found or deleted",
        )
    return ItemResponse.from_entity(entity)


@router.delete("/{item_id}")
async def delete_item_by_id(item_id: int) -> Response:
    delete_item(item_id)
    return Response("")
