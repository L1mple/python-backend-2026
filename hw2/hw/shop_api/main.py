from dataclasses import dataclass
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
from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
)


app = FastAPI(title="Shop API")


class ItemRequest(BaseModel):
    name: str
    price: NonNegativeFloat

    model_config = ConfigDict(extra="forbid")


class ItemPatchRequest(BaseModel):
    name: str | None = None
    price: NonNegativeFloat | None = None

    model_config = ConfigDict(extra="forbid")


class ItemResponse(ItemRequest):
    id: int
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


@dataclass(slots=True)
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False


items: dict[int, Item] = {}
carts: dict[int, dict[int, int]] = {}


def get_item_response(item: Item) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        name=item.name,
        price=item.price,
        deleted=item.deleted,
    )


def get_cart_response(cart_id: int) -> CartResponse:
    cart = carts[cart_id]
    cart_items = [
        CartItemResponse(
            id=item_id,
            name=items[item_id].name,
            quantity=quantity,
            available=not items[item_id].deleted,
        )
        for item_id, quantity in cart.items()
    ]
    price = sum(items[item_id].price * quantity for item_id, quantity in cart.items())

    return CartResponse(id=cart_id, items=cart_items, price=price)


def get_active_item(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> dict[str, int]:
    cart_id = len(carts) + 1
    carts[cart_id] = {}
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> CartResponse:
    if cart_id not in carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return get_cart_response(cart_id)


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

    for cart_id, cart in carts.items():
        cart_response = get_cart_response(cart_id)
        quantity = sum(cart.values())

        if min_price is not None and cart_response.price < min_price:
            continue
        if max_price is not None and cart_response.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart_response)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    if cart_id not in carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    get_active_item(item_id)

    cart = carts[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1
    return get_cart_response(cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
async def create_item(info: ItemRequest, response: Response) -> ItemResponse:
    item_id = len(items) + 1
    item = Item(id=item_id, name=info.name, price=info.price)
    items[item_id] = item
    response.headers["location"] = f"/item/{item_id}"
    return get_item_response(item)


@app.get("/item/{item_id}")
async def get_item(item_id: int) -> ItemResponse:
    return get_item_response(get_active_item(item_id))


@app.get("/item")
async def get_items(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    result = []

    for item in items.values():
        if item.deleted and not show_deleted:
            continue
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue

        result.append(get_item_response(item))

    return result[offset : offset + limit]


@app.put("/item/{item_id}", response_model=ItemResponse)
async def replace_item(item_id: int, info: ItemRequest) -> ItemResponse | Response:
    item = items.get(item_id)
    if item is None or item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    item.name = info.name
    item.price = info.price
    return get_item_response(item)


@app.patch("/item/{item_id}", response_model=ItemResponse)
async def update_item(item_id: int, info: ItemPatchRequest) -> ItemResponse | Response:
    item = items.get(item_id)
    if item is None or item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    if info.name is not None:
        item.name = info.name
    if info.price is not None:
        item.price = info.price

    return get_item_response(item)


@app.delete("/item/{item_id}")
async def delete_item(item_id: int) -> Response:
    item = items.get(item_id)
    if item is not None:
        item.deleted = True
    return Response(status_code=HTTPStatus.OK)


class ChatRooms:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, chat_name: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(chat_name, set()).add(websocket)

    def disconnect(self, chat_name: str, websocket: WebSocket) -> None:
        room = self.connections.get(chat_name)
        if room is None:
            return

        room.discard(websocket)
        if not room:
            del self.connections[chat_name]

    async def broadcast(self, chat_name: str, sender: WebSocket, message: str) -> None:
        for websocket in self.connections.get(chat_name, set()).copy():
            if websocket is not sender:
                await websocket.send_text(message)


chat_rooms = ChatRooms()


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    username = uuid4().hex[:8]
    await chat_rooms.connect(chat_name, websocket)

    try:
        while True:
            message = await websocket.receive_text()
            await chat_rooms.broadcast(chat_name, websocket, f"{username} :: {message}")
    except WebSocketDisconnect:
        chat_rooms.disconnect(chat_name, websocket)
