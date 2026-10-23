from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from .contracts import ItemPatchRequest, ItemRequest, ItemResponse
from ...store import queries
from ...store.database import SessionDependency


router = APIRouter(prefix="/item")


@router.post("", status_code=HTTPStatus.CREATED)
async def post_item(session: SessionDependency, body: ItemRequest) -> ItemResponse:
    item = await queries.add_item(session, body.name, body.price)
    return ItemResponse.from_entity(item)


@router.get("/{id}")
async def get_item(session: SessionDependency, id: int) -> ItemResponse:
    item = await queries.get_item(session, id)

    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return ItemResponse.from_entity(item)


@router.get("")
async def get_items(
    session: SessionDependency,
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: bool = False,
) -> list[ItemResponse]:
    items = await queries.get_items(
        session, offset, limit, min_price, max_price, show_deleted
    )
    return [ItemResponse.from_entity(item) for item in items]


@router.put("/{id}")
async def put_item(
    session: SessionDependency,
    id: int,
    body: ItemRequest,
) -> ItemResponse:
    item = await queries.update_item(session, id, body.name, body.price)

    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return ItemResponse.from_entity(item)


@router.patch("/{id}")
async def patch_item(
    session: SessionDependency,
    id: int,
    body: ItemPatchRequest,
) -> ItemResponse:
    item = await queries.get_item(session, id)

    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)

    patched_item = await queries.patch_item(session, id, body.name, body.price)
    return ItemResponse.from_entity(patched_item)


@router.delete("/{id}")
async def delete_item(session: SessionDependency, id: int) -> Response:
    await queries.delete_item(session, id)
    return Response()
