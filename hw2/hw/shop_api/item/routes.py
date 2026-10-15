from decimal import Decimal
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Response, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .contracts import (
    ItemRequest,
    ItemResponse,
    PatchItemRequest
)

import store.db.item as item_repo

from store.db.db import get_async_session

router = APIRouter()


@router.post("", status_code=HTTPStatus.CREATED)
async def add_item(
        info: ItemRequest,
        response: Response,
        session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ItemResponse:
    entity = await item_repo.add(session, info.as_item_info())

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
async def get_item(
        item_id: int,
        session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ItemResponse:
    entity = await item_repo.get_one(session, item_id)

    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{item_id} was not found",
        )
    return ItemResponse.from_entity(entity)


@router.get("", status_code=HTTPStatus.OK)
async def get_item_list(
        session: Annotated[AsyncSession, Depends(get_async_session)],
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1)] = 10,
        min_price: Annotated[Decimal | None, Query(ge=0)] = None,
        max_price: Annotated[Decimal | None, Query(ge=0)] = None,
        show_deleted: bool = False,
) -> list[ItemResponse]:
    entities = await item_repo.get_many(
        session,
        offset,
        limit,
        min_price,
        max_price,
        show_deleted,
    )
    return [ItemResponse.from_entity(e) for e in entities]


@router.put("/{item_id}",
            responses={
                HTTPStatus.OK: {
                    "description": "Successfully updated item",
                },
                HTTPStatus.NOT_MODIFIED: {
                    "description": "Failed to modify item as one was not found",
                },
            }, )
async def put_item(
        item_id: int,
        info: ItemRequest,
        session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ItemResponse:
    entity = await item_repo.update(session, item_id, info.as_item_info())

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
async def patch_item(
        item_id: int,
        info: PatchItemRequest,
        session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ItemResponse:
    entity = await item_repo.patch(session, item_id, info.as_patch_item_info())

    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{item_id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.delete("/{item_id}", status_code=HTTPStatus.OK)
async def delete_item(
        item_id: int,
        session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Response:
    await item_repo.delete(session, item_id)
    return Response("")
