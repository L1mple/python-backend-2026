from http import HTTPStatus
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt


from shop_api import store
from shop_api.database import get_db
from .contracts import ItemRequest, ItemResponse, PatchItemRequest

router = APIRouter(prefix="/item", tags=["item"])


@router.post("/", status_code=HTTPStatus.CREATED)
async def post_item(
    info: ItemRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> ItemResponse:
    item = await store.add_item(session, name=info.name, price=info.price)
    response.headers["location"] = f"/item/{item.id}"
    return ItemResponse.from_entity(item)


@router.get("/{id}")
async def get_item_by_id(
    id: int,
    session: AsyncSession = Depends(get_db),
) -> ItemResponse:
    item = await store.get_item(session, id)

    if item is None or item.deleted:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(item)


@router.get("/")
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
    session: AsyncSession = Depends(get_db),
) -> list[ItemResponse]:
    items = await store.get_items(
        session,
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )
    return [ItemResponse.from_entity(i) for i in items]


@router.put("/{id}")
async def put_item(
    id: int,
    info: ItemRequest,
    session: AsyncSession = Depends(get_db),
) -> ItemResponse:
    item = await store.update_item(session, id, name=info.name, price=info.price)

    if item is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(item)


@router.patch("/{id}")
async def patch_item(
    id: int,
    info: PatchItemRequest,
    session: AsyncSession = Depends(get_db),
) -> ItemResponse:
    existing = await store.get_item(session, id)

    if existing is None or existing.deleted:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not found or is deleted",
        )

    item = await store.patch_item(session, id, name=info.name, price=info.price)

    if item is None:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not found",
        )

    return ItemResponse.from_entity(item)


@router.delete("/{id}")
async def delete_item(
    id: int,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await store.delete_item(session, id)
    return Response("")