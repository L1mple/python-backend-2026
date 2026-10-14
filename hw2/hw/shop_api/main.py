from http import HTTPStatus
from typing import Annotated
from uuid import uuid4

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

app = FastAPI(title="Shop API")


class ItemInput(BaseModel):
    name: str
    price: float = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class ItemPatch(BaseModel):
    name: str | None = None
    price: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def reject_null_fields(self) -> "ItemPatch":
        """Не допускать null для обязательных полей товара."""
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("name and price cannot be null")
        return self


class Item(ItemInput):
    id: int
    deleted: bool = False


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


items: dict[int, Item] = {}
carts: dict[int, dict[int, int]] = {}
chat_rooms: dict[str, set[WebSocket]] = {}


def cart_view(cart_id: int) -> Cart:
    """Собрать корзину по текущему состоянию товаров."""
    quantities = carts.get(cart_id)
    if quantities is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    cart_items = [
        CartItem(
            id=item_id,
            name=items[item_id].name,
            quantity=quantity,
            available=not items[item_id].deleted,
        )
        for item_id, quantity in quantities.items()
    ]
    price = sum(
        items[item_id].price * quantity
        for item_id, quantity in quantities.items()
    )
    return Cart(id=cart_id, items=cart_items, price=price)


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response) -> dict[str, int]:
    cart_id = len(carts) + 1
    carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> Cart:
    return cart_view(cart_id)


@app.get("/cart")
def list_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[Cart]:
    result = []
    for cart_id, quantities in carts.items():
        cart = cart_view(cart_id)
        quantity = sum(quantities.values())
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(cart)
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int) -> Cart:
    if cart_id not in carts or item_id not in items or items[item_id].deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    quantities = carts[cart_id]
    quantities[item_id] = quantities.get(item_id, 0) + 1
    return cart_view(cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(info: ItemInput, response: Response) -> Item:
    item_id = len(items) + 1
    item = Item(id=item_id, **info.model_dump())
    items[item_id] = item
    response.headers["Location"] = f"/item/{item_id}"
    return item


@app.get("/item/{item_id}")
def get_item(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    return item


@app.get("/item")
def list_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
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
def replace_item(item_id: int, info: ItemInput) -> Item:
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    item.name = info.name
    item.price = info.price
    return item


@app.patch("/item/{item_id}", response_model=Item)
def patch_item(item_id: int, info: ItemPatch) -> Item | Response:
    item = items.get(item_id)
    if item is None or item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    for field, value in info.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> Response:
    item = items.get(item_id)
    if item is not None:
        item.deleted = True
    return Response(status_code=HTTPStatus.OK)


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    """Пересылать сообщения остальным участникам той же комнаты."""
    username = uuid4().hex[:8]
    await websocket.accept()
    room = chat_rooms.setdefault(chat_name, set())
    room.add(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            for participant in room.copy():
                if participant is not websocket:
                    await participant.send_text(f"{username} :: {message}")
    except WebSocketDisconnect:
        room.remove(websocket)
        if not room:
            del chat_rooms[chat_name]
