from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeInt, PositiveInt, PositiveFloat

from shop_api.store import item as store

from shop_api.api.item.contracts import (
    PatchItemRequest,
    ItemRequest,
    ItemResponse,
)

router = APIRouter(prefix="/item")


@router.get("/")
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[PositiveFloat | None, Query()] = None,
    max_price: Annotated[PositiveFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False
    ) -> list[ItemResponse]:
    return [ItemResponse.from_entity(e) 
            for e in store.get_many(offset, limit, min_price, max_price, show_deleted)]


@router.get(
    "/{id}",
    responses={
        HTTPStatus.OK: {
            "description": "Successfully returned requested item",
        },
        HTTPStatus.NOT_FOUND: {
            "description": "Failed to return requested item as one was not found",
        },
    },
)
async def get_item_by_id(id: int) -> ItemResponse:
    entity = store.get_one(id)

    if not entity:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.post(
    "/",
    status_code=HTTPStatus.CREATED,
)
async def post_item(info: ItemRequest, response: Response) -> ItemResponse:
    entity = store.add(info.as_item_info())

    # as REST states one should provide uri to newly created resource in location header
    response.headers["location"] = f"/item/{entity.id}"

    return ItemResponse.from_entity(entity)


@router.patch(
    "/{id}",
    responses={
        HTTPStatus.OK: {
            "description": "Successfully patched item",
        },
        HTTPStatus.NOT_MODIFIED: {
            "description": "Failed to modify item as one was not found",
        },
    },
)
async def patch_item(id: int, info: PatchItemRequest) -> ItemResponse:
    entity = store.patch(id, info.as_patch_item_info())

    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.put(
    "/{id}",
    responses={
        HTTPStatus.OK: {
            "description": "Successfully updated or upserted item",
        },
        HTTPStatus.NOT_MODIFIED: {
            "description": "Failed to modify item as one was not found",
        },
    }
)
async def put_item(
    id: int,
    info: ItemRequest,
    upsert: Annotated[bool, Query()] = False,
) -> ItemResponse:
    entity = (
        store.upsert(id, info.as_item_info())
        if upsert
        else store.update(id, info.as_item_info())
    )

    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.delete("/{id}")
async def delete_item(id: int) -> Response:
    if not store.delete(id):
        raise HTTPException(
            HTTPStatus.OK,
            f"Requested resource /item/{id} was not found",
        )
    return Response(status_code=HTTPStatus.OK)
