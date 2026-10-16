from shop_api import store
from http import HTTPStatus
from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from .contracts import ItemRequest, ItemResponse, PatchItemRequest

router = APIRouter(prefix="/item", tags=["item"])


@router.post("/", status_code=HTTPStatus.CREATED)
async def post_item(info: ItemRequest, response: Response) -> ItemResponse:
    entity = store.add_item(info.as_item_info())
    response.headers["location"] = f"/item/{entity.id}"
    return ItemResponse.from_entity(entity)


@router.get("/{id}")
async def get_item_by_id(id: int) -> ItemResponse:
    entity = store.get_item(id)

    if entity is None or entity.info.deleted:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.get("/")
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    entities = store.get_items(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )
    return [ItemResponse.from_entity(e) for e in entities]


@router.put("/{id}")
async def put_item(id: int, info: ItemRequest) -> ItemResponse:
    entity = store.update_item(id, info.as_item_info())

    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.patch("/{id}")
async def patch_item(id: int, info: PatchItemRequest) -> ItemResponse:
    existing = store.get_item(id)

    if existing is None or existing.info.deleted:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not found or is deleted",
        )

    entity = store.patch_item(id, info.as_patch_item_info())

    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(entity)


@router.delete("/{id}")
async def delete_item(id: int) -> Response:
    store.delete_item(id)
    return Response("")
