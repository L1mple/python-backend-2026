from dataclasses import dataclass, field
from http import HTTPStatus
from itertools import count
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, NonNegativeFloat, NonNegativeInt, PositiveInt

app = FastAPI(title="Shop API")


@dataclass(slots=True)
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class Cart:
    id: int
    items: dict[int, int] = field(default_factory=dict)


_items: dict[int, Item] = {}
_carts: dict[int, Cart] = {}
_item_ids = count()
_cart_ids = count()


class ItemRequest(BaseModel):
    name: str
    price: NonNegativeFloat


class ItemPatchRequest(BaseModel):
    name: str | None = None
    price: NonNegativeFloat | None = None

    model_config = ConfigDict(extra="forbid")


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float


def _item_response(item: Item) -> ItemResponse:
    return ItemResponse(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


def _cart_response(cart: Cart) -> CartResponse:
    items = []
    price = 0.0
    for item_id, quantity in cart.items.items():
        item = _items[item_id]
        items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        if not item.deleted:
            price += item.price * quantity
    return CartResponse(id=cart.id, items=items, price=price)


def _get_item_or_404(item_id: int) -> Item:
    item = _items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return item


def _get_cart_or_404(cart_id: int) -> Cart:
    cart = _carts.get(cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")
    return cart


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> dict[str, int]:
    cart = Cart(id=next(_cart_ids))
    _carts[cart.id] = cart
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> CartResponse:
    return _cart_response(_get_cart_or_404(cart_id))


@app.get("/cart")
async def get_carts(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    result = []
    for cart in _carts.values():
        resp = _cart_response(cart)
        quantity = sum(item.quantity for item in resp.items)
        if min_price is not None and resp.price < min_price:
            continue
        if max_price is not None and resp.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(resp)
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_to_cart(cart_id: int, item_id: int) -> CartResponse:
    cart = _get_cart_or_404(cart_id)
    item = _get_item_or_404(item_id)
    cart.items[item.id] = cart.items.get(item.id, 0) + 1
    return _cart_response(cart)


@app.post("/item", status_code=HTTPStatus.CREATED)
async def create_item(body: ItemRequest, response: Response) -> ItemResponse:
    item = Item(id=next(_item_ids), name=body.name, price=body.price)
    _items[item.id] = item
    response.headers["location"] = f"/item/{item.id}"
    return _item_response(item)


@app.get("/item/{item_id}")
async def get_item(item_id: int) -> ItemResponse:
    item = _get_item_or_404(item_id)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return _item_response(item)


@app.get("/item")
async def get_items(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    result = [
        _item_response(item)
        for item in _items.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return result[offset : offset + limit]


@app.put("/item/{item_id}")
async def replace_item(item_id: int, body: ItemRequest) -> ItemResponse:
    item = _get_item_or_404(item_id)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)
    item.name = body.name
    item.price = body.price
    return _item_response(item)


@app.patch("/item/{item_id}")
async def patch_item(item_id: int, body: ItemPatchRequest) -> ItemResponse:
    item = _get_item_or_404(item_id)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)
    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    return _item_response(item)


@app.delete("/item/{item_id}")
async def delete_item(item_id: int) -> ItemResponse:
    item = _get_item_or_404(item_id)
    item.deleted = True
    return _item_response(item)


_rooms: dict[str, set[WebSocket]] = {}


@app.websocket("/chat/{chat_name}")
async def chat(ws: WebSocket, chat_name: str) -> None:
    await ws.accept()
    username = f"user-{uuid4().hex[:6]}"
    room = _rooms.setdefault(chat_name, set())
    room.add(ws)
    try:
        while True:
            text = await ws.receive_text()
            for other in list(room):
                if other is not ws:
                    await other.send_text(f"{username} :: {text}")
    except WebSocketDisconnect:
        room.discard(ws)
        if not room:
            _rooms.pop(chat_name, None)