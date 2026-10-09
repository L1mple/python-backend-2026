from typing import Annotated

from fastapi import APIRouter, Query

from shop_api import storage
from shop_api.database import DatabaseSession
from shop_api.schemas import ItemCreate, ItemPatch, ItemReplace, ItemResponse


router = APIRouter(prefix="/item", tags=["items"])


@router.post("", response_model=ItemResponse, status_code=201)
def create_item(body: ItemCreate, session: DatabaseSession):
    return storage.create_item(session, name=body.name, price=body.price)


@router.get("", response_model=list[ItemResponse])
def list_items(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
):
    return storage.list_items(
        session,
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )


@router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, session: DatabaseSession):
    return storage.get_item(session, item_id)


@router.put("/{item_id}", response_model=ItemResponse)
def replace_item(item_id: int, body: ItemReplace, session: DatabaseSession):
    return storage.replace_item(session, item_id, name=body.name, price=body.price)


@router.patch("/{item_id}", response_model=ItemResponse)
def patch_item(item_id: int, body: ItemPatch, session: DatabaseSession):
    changes = body.model_dump(exclude_unset=True)
    return storage.patch_item(session, item_id, changes=changes)


@router.delete("/{item_id}", status_code=200)
def delete_item(item_id: int, session: DatabaseSession):
    storage.delete_item(session, item_id)
    return {"detail": "Item deleted"}
