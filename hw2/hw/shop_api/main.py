from collections import defaultdict
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, field_validator

app = FastAPI(title="Shop API")


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: Annotated[float, Field(ge=0)]


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: Annotated[float | None, Field(ge=0)] = None

    @field_validator("name", "price")
    @classmethod
    def reject_null(cls, value: str | float | None) -> str | float:
        if value is None:
            raise ValueError("value must not be null")
        return value


items: dict[int, dict] = {}
carts: dict[int, dict[int, int]] = {}
next_item_id = 1
next_cart_id = 1


def item_or_404(item_id: int, include_deleted: bool = False) -> dict:
    item = items.get(item_id)
    if item is None or (item["deleted"] and not include_deleted):
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def cart_or_404(cart_id: int) -> dict[int, int]:
    cart = carts.get(cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


def cart_response(cart_id: int) -> dict:
    cart = carts[cart_id]
    cart_items = [
        {
            "id": item_id,
            "name": items[item_id]["name"],
            "quantity": quantity,
            "available": not items[item_id]["deleted"],
        }
        for item_id, quantity in cart.items()
    ]
    price = sum(items[item_id]["price"] * quantity for item_id, quantity in cart.items())
    return {"id": cart_id, "items": cart_items, "price": price}


@app.post("/cart", status_code=201)
def create_cart(response: Response) -> dict[str, int]:
    global next_cart_id

    cart_id = next_cart_id
    next_cart_id += 1
    carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> dict:
    cart_or_404(cart_id)
    return cart_response(cart_id)


@app.get("/cart")
def get_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[dict]:
    result = []
    for cart_id, cart in carts.items():
        data = cart_response(cart_id)
        quantity = sum(cart.values())
        if min_price is not None and data["price"] < min_price:
            continue
        if max_price is not None and data["price"] > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(data)
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int) -> dict:
    cart = cart_or_404(cart_id)
    item_or_404(item_id)
    cart[item_id] = cart.get(item_id, 0) + 1
    return cart_response(cart_id)


@app.post("/item", status_code=201)
def create_item(data: ItemCreate, response: Response) -> dict:
    global next_item_id

    item_id = next_item_id
    next_item_id += 1
    item = {"id": item_id, **data.model_dump(), "deleted": False}
    items[item_id] = item
    response.headers["Location"] = f"/item/{item_id}"
    return item


@app.get("/item/{item_id}")
def get_item(item_id: int) -> dict:
    return item_or_404(item_id)


@app.get("/item")
def get_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[dict]:
    result = [
        item
        for item in items.values()
        if (show_deleted or not item["deleted"])
        and (min_price is None or item["price"] >= min_price)
        and (max_price is None or item["price"] <= max_price)
    ]
    return result[offset : offset + limit]


@app.put("/item/{item_id}")
def replace_item(item_id: int, data: ItemCreate) -> dict:
    old_item = item_or_404(item_id, include_deleted=True)
    item = {"id": item_id, **data.model_dump(), "deleted": old_item["deleted"]}
    items[item_id] = item
    return item


@app.patch("/item/{item_id}")
def update_item(item_id: int, data: ItemPatch):
    item = item_or_404(item_id, include_deleted=True)
    if item["deleted"]:
        return Response(status_code=304)
    item.update(data.model_dump(exclude_unset=True))
    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> dict[str, int]:
    item = item_or_404(item_id, include_deleted=True)
    item["deleted"] = True
    return {"id": item_id}


chat_rooms: dict[str, dict[WebSocket, str]] = defaultdict(dict)


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()
    username = uuid4().hex[:8]
    chat_rooms[chat_name][websocket] = username

    try:
        while True:
            message = await websocket.receive_text()
            text = f"{username} :: {message}"
            for client in list(chat_rooms[chat_name]):
                if client is not websocket:
                    try:
                        await client.send_text(text)
                    except (WebSocketDisconnect, RuntimeError):
                        chat_rooms[chat_name].pop(client, None)
    except WebSocketDisconnect:
        pass
    finally:
        room = chat_rooms.get(chat_name)
        if room is not None:
            room.pop(websocket, None)
            if not room:
                del chat_rooms[chat_name]
