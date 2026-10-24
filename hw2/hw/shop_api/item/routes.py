from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

import store
from .contracts import ItemRequest, ItemResponse, PatchItemRequest


router = APIRouter(prefix="/item")


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
)
async def post_item(
    info: ItemRequest,
    response: Response,
) -> ItemResponse:
    entity = store.add(
        info.as_item_info(),
    )

    response.headers["location"] = f"/item/{entity.id}"

    return ItemResponse.from_entity(entity)


@router.get("")
async def get_item_list(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[
        float | None,
        Query(ge=0),
    ] = None,
    max_price: Annotated[
        float | None,
        Query(ge=0),
    ] = None,
    show_deleted: bool = False,
) -> list[ItemResponse]:
    entities = store.get_many(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )

    return [
        ItemResponse.from_entity(entity)
        for entity in entities
    ]


@router.get("/{id}")
async def get_item(
    id: int,
) -> ItemResponse:
    entity = store.get_one(id)

    if entity is None or entity.info.deleted:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    return ItemResponse.from_entity(entity)


@router.put("/{id}")
async def put_item(
    id: int,
    info: ItemRequest,
):
    current = store.get_one(id)

    if current is None or current.info.deleted:
        return Response(
            status_code=HTTPStatus.NOT_MODIFIED,
        )

    entity = store.update(
        id,
        info.as_item_info(),
    )

    return ItemResponse.from_entity(entity)


@router.patch("/{id}")
async def patch_item(
    id: int,
    info: PatchItemRequest,
):
    entity = store.patch(
        id,
        info.as_patch_item_info(),
    )

    if entity is None:
        return Response(
            status_code=HTTPStatus.NOT_MODIFIED,
        )

    return ItemResponse.from_entity(entity)


@router.delete("/{id}")
async def delete_item(
    id: int,
) -> Response:
    store.delete(id)

    return Response(
        status_code=HTTPStatus.OK,
    )