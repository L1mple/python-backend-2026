import random
import string
from dataclasses import dataclass, field
from http import HTTPStatus
from itertools import count
from typing import Optional

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="Shop API")


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    price: Optional[float] = None


class Item(BaseModel):
    id: int
    name: str
    price: float
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

_item_id_seq = count(1)
_cart_id_seq = count(1)

items_db: dict[int, Item] = {}
carts_db: dict[int, dict[int, int]] = {}


def build_cart(cart_id: int) -> Cart:
    items: list[CartItem] = []
    total = 0.0

    for item_id, quantity in carts_db[cart_id].items():
        item = items_db[item_id]
        items.append(
            CartItem(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        total += item.price * quantity

    return Cart(id=cart_id, items=items, price=total)


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response) -> dict:
    cart_id = next(_cart_id_seq)
    carts_db[cart_id] = {}
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> Cart:
    if cart_id not in carts_db:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return build_cart(cart_id)


@app.get("/cart")
def get_cart_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
) -> list[Cart]:
    result: list[Cart] = []

    for cart_id in carts_db:
        cart = build_cart(cart_id)
        total_quantity = sum(i.quantity for i in cart.items)

        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int) -> Cart:
    if cart_id not in carts_db:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    if item_id not in items_db:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")

    cart_items = carts_db[cart_id]
    cart_items[item_id] = cart_items.get(item_id, 0) + 1
    return build_cart(cart_id)

@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(body: ItemCreate, response: Response) -> Item:
    item = Item(id=next(_item_id_seq), name=body.name, price=body.price)
    items_db[item.id] = item
    response.headers["location"] = f"/item/{item.id}"
    return item


@app.get("/item/{item_id}")
def get_item(item_id: int) -> Item:
    item = items_db.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


@app.get("/item")
def get_item_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = False,
) -> list[Item]:
    result = [
        item
        for item in items_db.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return result[offset : offset + limit]


@app.put("/item/{item_id}")
def replace_item(item_id: int, body: ItemCreate) -> Item:
    item = items_db.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")

    item.name = body.name
    item.price = body.price
    return item


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatch):
    item = items_db.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> dict:
    item = items_db.get(item_id)
    if item is not None:
        item.deleted = True
    return {}


@dataclass
class ChatRoom:
    members: dict[WebSocket, str] = field(default_factory=dict)


chat_rooms: dict[str, ChatRoom] = {}


def random_username() -> str:
    return "user_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()

    room = chat_rooms.setdefault(chat_name, ChatRoom())
    username = random_username()
    room.members[websocket] = username

    try:
        while True:
            message = await websocket.receive_text()
            text = f"{username} :: {message}"

            for member in list(room.members):
                if member is not websocket:
                    await member.send_text(text)
    except WebSocketDisconnect:
        pass
    finally:
        room.members.pop(websocket, None)
        if not room.members:
            chat_rooms.pop(chat_name, None)
