from decimal import Decimal
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Response, Query, HTTPException

from .contracts import (
    ItemRequest,
    ItemResponse,
    PatchItemRequest
)

from hw2.hw.store import item as item_repo

router = APIRouter()


@router.post("", status_code=HTTPStatus.CREATED)
async def add_item(info: ItemRequest, response: Response) -> ItemResponse:
    entity = item_repo.add(info.as_item_info())

    response.headers["Location"] = f"/item/{entity.id}"

    return ItemResponse.from_entity(entity)


@router.get(
    "/{item_id}",
    responses={
        HTTPStatus.OK: {
            "description": "Successfully returned requested item",
        },
        HTTPStatus.NOT_FOUND: {
            "description": "Failed to return requested item as one was not found",
        },
    },
)
async def get_item(item_id: int) -> ItemResponse:
    entity = item_repo.get_one(item_id)

    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{item_id} was not found",
        )
    return ItemResponse.from_entity(entity)


@router.get("", status_code=HTTPStatus.OK)
async def get_item_list(
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1)] = 10,
        min_price: Annotated[Decimal | None, Query(ge=0)] = None,
        max_price: Annotated[Decimal | None, Query(ge=0)] = None,
        show_deleted: bool = False,
) -> list[ItemResponse]:
    return [ItemResponse.from_entity(e) for e in
            item_repo.get_many(
                offset,
                limit,
                min_price,
                max_price,
                show_deleted
            )]


@router.put("/{item_id}",
            responses={
                HTTPStatus.OK: {
                    "description": "Successfully updated item",
                },
                HTTPStatus.NOT_MODIFIED: {
                    "description": "Failed to modify item as one was not found",
                },
            }, )
async def put_item(item_id: int, info: ItemRequest) -> ItemResponse:
    entity = item_repo.update(item_id, info.as_item_info())

    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{item_id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.patch("/{item_id}",
              responses={
                  HTTPStatus.OK: {
                      "description": "Successfully patched item",
                  },
                  HTTPStatus.NOT_MODIFIED: {
                      "description": "Failed to modify item as one was not found",
                  },
              }, )
async def patch_item(item_id: int, info: PatchItemRequest) -> ItemResponse:
    entity = item_repo.patch(item_id, info.as_patch_item_info())

    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{item_id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.delete("/{item_id}", status_code=HTTPStatus.OK)
async def delete_item(item_id: int) -> Response:
    item_repo.delete(item_id)
    return Response("")
