from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from shop_api import metrics, storage
from shop_api.contracts import ItemPatchRequest, ItemRequest, ItemResponse
from shop_api.db import SessionDep
from shop_api.models import Item

router = APIRouter(prefix="/item", tags=["item"])


async def _get_item_or_404(
    session: AsyncSession,
    item_id: int,
    *,
    for_update: bool = False,
) -> Item:
    item = await storage.get_item(session, item_id, for_update=for_update)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return item


async def _get_editable_item(session: AsyncSession, item_id: int) -> Item:
    item = await _get_item_or_404(session, item_id, for_update=True)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)
    return item


@router.post("", status_code=HTTPStatus.CREATED)
async def create_item(body: ItemRequest, response: Response, session: SessionDep) -> ItemResponse:
    item = await storage.add_item(session, body.name, body.price)
    metrics.ITEMS_CREATED.inc()
    response.headers["location"] = f"/item/{item.id}"
    return ItemResponse.from_item(item)


@router.get("/{item_id}")
async def get_item(item_id: int, session: SessionDep) -> ItemResponse:
    item = await _get_item_or_404(session, item_id)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return ItemResponse.from_item(item)


@router.get("")
async def list_items(
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[ItemResponse]:
    items = await storage.list_items(session, offset, limit, min_price, max_price, show_deleted)
    return [ItemResponse.from_item(item) for item in items]


@router.put("/{item_id}")
async def replace_item(item_id: int, body: ItemRequest, session: SessionDep) -> ItemResponse:
    item = await _get_editable_item(session, item_id)
    item.name = body.name
    item.price = body.price
    await session.commit()
    return ItemResponse.from_item(item)


@router.patch("/{item_id}")
async def update_item(item_id: int, body: ItemPatchRequest, session: SessionDep) -> ItemResponse:
    item = await _get_editable_item(session, item_id)
    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    await session.commit()
    return ItemResponse.from_item(item)


@router.delete("/{item_id}")
async def delete_item(item_id: int, session: SessionDep) -> ItemResponse:
    # Повторное удаление тоже отвечает 200: результат тот же
    item = await _get_item_or_404(session, item_id, for_update=True)
    if not item.deleted:
        item.deleted = True
        await session.commit()
        metrics.ITEMS_DELETED.inc()
    return ItemResponse.from_item(item)
