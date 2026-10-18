from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from shop_api import crud
from shop_api.contracts import ItemCreate, ItemPatch, ItemResponse, ItemUpdate
from shop_api.database import get_session

router = APIRouter(prefix="/item", tags=["item"])


@router.post("", status_code=HTTPStatus.CREATED)
def create_item(
    payload: ItemCreate,
    session: Session = Depends(get_session),
) -> ItemResponse:
    item = crud.create_item(session, payload.name, payload.price)
    return ItemResponse(**item)


@router.get("")
def list_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
    session: Session = Depends(get_session),
) -> list[ItemResponse]:
    found = crud.list_items(session, offset, limit, min_price, max_price, show_deleted)
    return [ItemResponse(**item) for item in found]


@router.get("/{item_id}")
def get_item(
    item_id: int,
    session: Session = Depends(get_session),
) -> ItemResponse:
    item = crud.get_item(session, item_id)
    if item is None or item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return ItemResponse(**item)


@router.put("/{item_id}")
def replace_item(
    item_id: int,
    payload: ItemUpdate,
    session: Session = Depends(get_session),
) -> ItemResponse:
    existing = crud.get_item(session, item_id)
    if existing is None or existing["deleted"]:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} not found")
    updated = crud.replace_item(session, item_id, payload.name, payload.price)
    return ItemResponse(**updated)


@router.patch("/{item_id}")
def patch_item(
    item_id: int,
    payload: ItemPatch,
    session: Session = Depends(get_session),
):
    existing = crud.get_item(session, item_id)
    if existing is None or existing["deleted"]:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    updated = crud.patch_item(session, item_id, payload.name, payload.price)
    return ItemResponse(**updated)


@router.delete("/{item_id}")
def delete_item(
    item_id: int,
    session: Session = Depends(get_session),
) -> ItemResponse:
    item = crud.get_item(session, item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    crud.mark_item_deleted(session, item_id)
    return ItemResponse(**item)
