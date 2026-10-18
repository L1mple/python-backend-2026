from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from shop_api import store

from .contracts import ItemRequest, ItemResponse, PatchItemRequest

router = APIRouter(prefix="/item", tags=["item"])


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    responses={
        HTTPStatus.CREATED: {"description": "Successfully created new item"},
    },
)
async def post_item(info: ItemRequest, response: Response) -> ItemResponse:
    entity = store.add_item(info.as_item_info())

    # REST предписывает отдавать ссылку на созданный ресурс в заголовке location
    response.headers["location"] = f"/item/{entity.id}"

    return ItemResponse.from_entity(entity)


@router.get(
    "",
    responses={
        HTTPStatus.OK: {"description": "Successfully returned list of items"},
    },
)
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    entities = store.get_many_items(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )

    return [ItemResponse.from_entity(entity) for entity in entities]


@router.get(
    "/{id}",
    responses={
        HTTPStatus.OK: {"description": "Successfully returned requested item"},
        HTTPStatus.NOT_FOUND: {"description": "Requested item was not found"},
    },
)
async def get_item_by_id(id: int) -> ItemResponse:
    entity = store.get_item(id)

    if entity is None or entity.info.deleted:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.put(
    "/{id}",
    responses={
        HTTPStatus.OK: {"description": "Successfully replaced item"},
        HTTPStatus.NOT_FOUND: {
            "description": "Failed to replace item as one was not found",
        },
    },
)
async def put_item(id: int, info: ItemRequest) -> ItemResponse:
    entity = store.update_item(id, info.as_item_info())

    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.patch(
    "/{id}",
    responses={
        HTTPStatus.OK: {"description": "Successfully patched item"},
        HTTPStatus.NOT_MODIFIED: {
            "description": "Failed to patch item as one was not found or deleted",
        },
    },
)
async def patch_item(id: int, info: PatchItemRequest) -> ItemResponse:
    entity = store.patch_item(id, info.as_patch_item_info())

    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not modified",
        )

    return ItemResponse.from_entity(entity)


@router.delete(
    "/{id}",
    responses={
        HTTPStatus.OK: {"description": "Item is marked as deleted"},
    },
)
async def delete_item(id: int) -> Response:
    # удаление идемпотентно: повторный вызов так же успешен
    store.delete_item(id)

    return Response(status_code=HTTPStatus.OK)
