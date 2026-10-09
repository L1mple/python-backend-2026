import random
from collections import defaultdict
from itertools import count
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="Shop API")

# hw3: экспортирует /metrics для Prometheus
Instrumentator().instrument(app).expose(app)


# --------------------------------------------------------------------------
# Модели
# --------------------------------------------------------------------------


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False


class ItemCreateRequest(BaseModel):
    name: str
    price: float


class ItemPutRequest(BaseModel):
    name: str
    price: float


class ItemPatchRequest(BaseModel):
    # extra="forbid" отклоняет как неизвестные поля, так и попытку поменять
    # "deleted" (его в модели просто нет).
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    price: Optional[float] = None


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


# --------------------------------------------------------------------------
# Хранилище (в памяти)
# --------------------------------------------------------------------------

_items: dict[int, Item] = {}
_item_id_seq = count(1)

# cart_id -> {item_id: quantity}
_carts: dict[int, dict[int, int]] = {}
_cart_id_seq = count(1)


def _get_item_or_404(item_id: int) -> Item:
    """Ищет товар независимо от флага deleted (нужно для PUT/PATCH/DELETE)."""
    item = _items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _get_visible_item_or_404(item_id: int) -> Item:
    """Для публичного GET: удалённый товар считается не найденным."""
    item = _get_item_or_404(item_id)
    if item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _build_cart(cart_id: int) -> Cart:
    quantities = _carts[cart_id]
    cart_items: list[CartItem] = []
    price = 0.0

    for item_id, quantity in quantities.items():
        item = _items.get(item_id)
        if item is None:
            continue
        cart_items.append(
            CartItem(id=item.id, name=item.name, quantity=quantity, available=not item.deleted)
        )
        price += item.price * quantity

    return Cart(id=cart_id, items=cart_items, price=price)


# --------------------------------------------------------------------------
# item
# --------------------------------------------------------------------------


@app.post("/item", status_code=201, response_model=Item)
def create_item(body: ItemCreateRequest) -> Item:
    item_id = next(_item_id_seq)
    item = Item(id=item_id, name=body.name, price=body.price, deleted=False)
    _items[item_id] = item
    return item


@app.get("/item/{item_id}", response_model=Item)
def get_item(item_id: int) -> Item:
    return _get_visible_item_or_404(item_id)


@app.get("/item", response_model=list[Item])
def get_item_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = Query(False),
) -> list[Item]:
    result: list[Item] = []
    for item_id in sorted(_items):
        item = _items[item_id]
        if not show_deleted and item.deleted:
            continue
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue
        result.append(item)

    return result[offset : offset + limit]


@app.put("/item/{item_id}", response_model=Item)
def put_item(item_id: int, body: ItemPutRequest) -> Item:
    item = _get_item_or_404(item_id)
    item.name = body.name
    item.price = body.price
    return item


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatchRequest):
    item = _get_item_or_404(item_id)

    if item.deleted:
        return Response(status_code=304)

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price

    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> Item:
    item = _get_item_or_404(item_id)
    item.deleted = True
    return item


# --------------------------------------------------------------------------
# cart
# --------------------------------------------------------------------------


@app.post("/cart", status_code=201)
def create_cart(response: Response) -> dict[str, int]:
    cart_id = next(_cart_id_seq)
    _carts[cart_id] = {}
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}", response_model=Cart)
def get_cart(cart_id: int) -> Cart:
    if cart_id not in _carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    return _build_cart(cart_id)


@app.get("/cart", response_model=list[Cart])
def get_cart_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
) -> list[Cart]:
    result: list[Cart] = []
    for cart_id in sorted(_carts):
        cart = _build_cart(cart_id)
        total_quantity = sum(ci.quantity for ci in cart.items)

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


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
def add_item_to_cart(cart_id: int, item_id: int) -> Cart:
    if cart_id not in _carts:
        raise HTTPException(status_code=404, detail="Cart not found")

    _get_item_or_404(item_id)  # товар должен существовать (удалённый тоже ок)

    quantities = _carts[cart_id]
    quantities[item_id] = quantities.get(item_id, 0) + 1

    return _build_cart(cart_id)


# --------------------------------------------------------------------------
# Доп. задание: WebSocket чат по комнатам
# --------------------------------------------------------------------------

_chat_rooms: dict[str, dict[WebSocket, str]] = defaultdict(dict)


def _random_username() -> str:
    return f"user-{random.randint(1000, 9999)}"


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()

    username = _random_username()
    room = _chat_rooms[chat_name]
    room[websocket] = username

    try:
        while True:
            message = await websocket.receive_text()
            formatted = f"{username} :: {message}"
            for peer in list(room):
                if peer is websocket:
                    continue
                await peer.send_text(formatted)
    except WebSocketDisconnect:
        pass
    finally:
        room.pop(websocket, None)
        if not room:
            _chat_rooms.pop(chat_name, None)