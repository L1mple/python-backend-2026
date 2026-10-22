import random
import string
from http import HTTPStatus
from fastapi import FastAPI, HTTPException, Query, WebSocket, Response, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Shop API")

Instrumentator().instrument(app).expose(app)

class ItemCreate(BaseModel):
    name: str
    price: float = Field(ge = 0)

class Item(ItemCreate):
    id: int
    deleted: bool = False

class ItemUpdate(BaseModel):
    name: str
    price: float = Field(ge = 0)

class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    price: Optional[float] = Field(default = None, ge = 0)


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool

class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float

items_dct = dict()
carts_dct = dict()
next_item_id = 1
next_cart_id = 1


def get_next_item_id() -> int:
    global next_item_id
    item_id = next_item_id
    next_item_id += 1
    return item_id


def get_next_cart_id() -> int:
    global next_cart_id
    cart_id = next_cart_id
    next_cart_id += 1
    return cart_id


def build_cart(cart_id: int) -> Cart:
    if cart_id not in carts_dct:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    cart_items = []
    total_price = 0
    for item_id, quantity in carts_dct[cart_id].items():
        item = items_dct.get(item_id)
        if item is None:
            continue
        cart_items.append(CartItem(id=item_id, name = item.name, quantity = quantity, available = not item.deleted))
        total_price += item.price * quantity
    return Cart(id = cart_id, items = cart_items, price = total_price)


# Item(REST)

@app.post("/item", status_code=HTTPStatus.CREATED, response_model = Item)
def create_item(item: ItemCreate) -> Item:
    item_id = get_next_item_id()
    new_item = Item(id = item_id, name = item.name, price = item.price, deleted=False)
    items_dct[item_id] = new_item
    return new_item

@app.get("/item/{item_id}", response_model = Item)
def get_item(item_id: int) -> Item:
    item = items_dct.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return item


@app.get("/item", response_model = list[Item])
def get_items(offset: int = Query(0, ge=0), limit: int = Query(10, gt=0), min_price: Optional[float] = Query(None, ge=0), max_price: Optional[float] = Query(None, ge=0), show_deleted: bool = Query(False)) -> list[Item]:
    result = []
    for item in items_dct.values():
        if not show_deleted and item.deleted:
            continue
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue
        result.append(item)

    result.sort(key=lambda x: x.id)
    return result[offset : offset + limit]

@app.put("/item/{item_id}", response_model = Item)
def put_item(item_id: int, item: ItemUpdate) -> Item:
    existing = items_dct.get(item_id)
    if existing is None or existing.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    updated = Item(id=item_id, name = item.name, price = item.price, deleted=existing.deleted)
    items_dct[item_id] = updated
    return updated

@app.patch("/item/{item_id}", response_model = Item)
def patch_item(item_id: int, patch: ItemPatch) -> Item:
    existing = items_dct.get(item_id)
    if existing is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    if existing.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_MODIFIED)
    update_data = patch.model_dump(exclude_unset=True)
    if not update_data:
        return existing
    updated = existing.model_copy(update = update_data)
    items_dct[item_id] = updated
    return updated


@app.delete("/item/{item_id}", response_model = Item)
def delete_item(item_id: int) -> Item:
    item = items_dct.get(item_id)
    if item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    item.deleted = True
    return item


# Cart(REST)

@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response) -> dict[str, int]:
    cart_id = get_next_cart_id()
    carts_dct[cart_id] = dict()
    response.headers['location'] = f"/cart/{cart_id}"
    return {'id': cart_id}

@app.get("/cart/{cart_id}", response_model = Cart)
def get_cart(cart_id: int) -> Cart:
    return build_cart(cart_id)

@app.get("/cart", response_model =list[Cart])
def get_carts(offset: int = Query(0, ge=0), limit: int = Query(10, gt=0), min_price: Optional[float] = Query(None, ge=0), max_price: Optional[float] = Query(None, ge=0),  min_quantity: Optional[int] = Query(None, ge=0), max_quantity: Optional[int] = Query(None, ge=0)) -> list[Cart]:
    result = []
    for cart_id in sorted(carts_dct.keys()):
        cart = build_cart(cart_id)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        total_quantity = sum(c.quantity for c in cart.items)
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue
        result.append(cart)

    return result[offset : offset + limit]

@app.post("/cart/{cart_id}/add/{item_id}", response_model = Cart)
def add_item_to_cart(cart_id: int, item_id: int) -> Cart:
    if cart_id not in carts_dct:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    item = items_dct.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    cart = carts_dct[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1
    return build_cart(cart_id)

# Web Sockets Chat

class ChatManager:
    def __init__(self) -> None:
        self.chats = dict()
    async def connect(self, chat_name: str, websocket: WebSocket) -> str:
        await websocket.accept()
        username = "".join(random.choices(string.ascii_letters+string.digits, k=10))
        self.chats.setdefault(chat_name, []).append((websocket, username))
        return username
    def disconnect(self, chat_name: str, websocket: WebSocket) -> None:
        chat = self.chats.get(chat_name, [])
        self.chats[chat_name] = [(ws, name) for ws, name in chat if ws is not websocket]
        if not self.chats[chat_name]:
            del self.chats[chat_name]

    async def broadcast(self, chat_name: str, sender: WebSocket, message: str, username: str) -> None:
        for ws, _ in self.chats.get(chat_name, []):
            if ws is not sender:
                await ws.send_text(f'{username} :: {message}')


chat_manager = ChatManager()

@app.websocket("/chat/{chat_name}")
async def chat_endpoint(websocket: WebSocket, chat_name: str) -> None:
    username = await chat_manager.connect(chat_name, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await chat_manager.broadcast(chat_name, websocket, message, username)
    except WebSocketDisconnect:
        chat_manager.disconnect(chat_name, websocket)