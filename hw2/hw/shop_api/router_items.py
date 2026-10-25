from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import NonNegativeInt, PositiveFloat, PositiveInt
from sqlalchemy.orm import Session

from store import queries
from store import MutateErrors

from .contracts import (
    ItemResponse,
    ItemRequest,
    PatchItemRequest,
)
from .session import get_session

router = APIRouter(prefix="/item", tags=["item"])


@router.get("")
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[PositiveFloat | None, Query()] = None,
    max_price: Annotated[PositiveFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
    session: Session = Depends(get_session),
) -> list[ItemResponse]:
    return [
        ItemResponse.from_entity(e)
        for e in queries.get_item_multiple(
            session,
            offset=offset,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            show_deleted=show_deleted,
        )
    ]


@router.get(
    "/{id}",
    responses={
        HTTPStatus.OK: {"description": "Successfully returned requested item"},
        HTTPStatus.NOT_FOUND: {"description": "Item was not found"},
    },
)
async def get_item_by_id(
    id: int,
    session: Session = Depends(get_session),
) -> ItemResponse:
    entity = queries.get_item(session, id)
    if entity is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Requested resource /item/{id} was not found",
        )
    return ItemResponse.from_entity(entity)


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
)
async def post_item(
    info: ItemRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> ItemResponse:
    entity = queries.add_item(session, info.as_add_item_info())
    response.headers["location"] = f"/item/{entity.id}"
    return ItemResponse.from_entity(entity)


@router.put(
    "/{id}",
    responses={
        HTTPStatus.OK: {"description": "Successfully updated item"},
        HTTPStatus.NOT_FOUND: {"description": "Item was not found"},
        HTTPStatus.NOT_MODIFIED: {"description": "Item is deleted"},
    },
)
async def put_item(
    id: int,
    info: ItemRequest,
    session: Session = Depends(get_session),
) -> ItemResponse:
    result = queries.put_item(session, id, info.as_add_item_info())
    if isinstance(result, MutateErrors):
        raise HTTPException(result.value, f"Failed to update /item/{id}: {result.name}")
    return ItemResponse.from_entity(result)


@router.patch(
    "/{id}",
    responses={
        HTTPStatus.OK: {"description": "Successfully patched item"},
        HTTPStatus.NOT_FOUND: {"description": "Item was not found"},
        HTTPStatus.NOT_MODIFIED: {"description": "Item is deleted"},
    },
)
async def patch_item(
    id: int,
    info: PatchItemRequest,
    session: Session = Depends(get_session),
) -> ItemResponse:
    result = queries.patch_item(session, id, info.as_patch_item_info())
    if isinstance(result, MutateErrors):
        raise HTTPException(result.value, f"Failed to patch /item/{id}: {result.name}")
    return ItemResponse.from_entity(result)


@router.delete("/{id}")
async def delete_item(
    id: int,
    session: Session = Depends(get_session),
) -> Response:
    queries.delete_item(session, id)
    return Response("")