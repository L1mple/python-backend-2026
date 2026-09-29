from http import HTTPStatus
from itertools import count
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, NonNegativeFloat, NonNegativeInt, PositiveInt

app = FastAPI(title="Shop API")


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False


class ItemRequest(BaseModel):
    name: str
    price: NonNegativeFloat


class PatchItemRequest(BaseModel):
    # deleted veya baska alan gelirse 422
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: NonNegativeFloat | None = None


items: dict[int, Item] = {}
item_ids = count(1)


def get_item_or_404(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return item


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(body: ItemRequest, response: Response) -> Item:
    item = Item(id=next(item_ids), name=body.name, price=body.price)
    items[item.id] = item
    response.headers["location"] = f"/item/{item.id}"
    return item


@app.get("/item/{item_id}")
def get_item(item_id: int) -> Item:
    return get_item_or_404(item_id)


@app.get("/item")
def get_items(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: bool = False,
) -> list[Item]:
    result = [
        item
        for item in items.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return result[offset : offset + limit]


@app.put("/item/{item_id}")
def replace_item(item_id: int, body: ItemRequest) -> Item:
    item = get_item_or_404(item_id)
    item.name = body.name
    item.price = body.price
    return item


@app.patch("/item/{item_id}")
def update_item(item_id: int, body: PatchItemRequest) -> Item:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    if item.deleted:
        # 304 body olmadan donmeli
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    # gercekten silmiyoruz, sadece isaretliyoruz
    item.deleted = True
    return item
