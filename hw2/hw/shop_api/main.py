"""REST/RPC shop API and a WebSocket chat with separate rooms."""

from http import HTTPStatus
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator, metrics

from .chat import ChatRooms
from .models import Cart, CartCreated, Item, ItemData, ItemPatch
from .store import ShopStore

app = FastAPI(title="Shop API")
Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["^/metrics$", "^/docs$", "^/redoc$", "^/openapi.json$"],
).add(
    metrics.default(
        latency_highr_buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10),
    )
).instrument(app).expose(app, include_in_schema=False)
store = ShopStore()
chat_rooms = ChatRooms()

Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(gt=0)]
PriceFilter = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]
QuantityFilter = Annotated[int | None, Query(ge=0)]


def require_item(item_id: int, *, include_deleted: bool = False) -> Item:
    item = store.items.get(item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


def require_cart(cart_id: int) -> None:
    if cart_id not in store.carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")


@app.post("/cart", status_code=HTTPStatus.CREATED, tags=["cart"])
async def create_cart(response: Response) -> CartCreated:
    cart_id = store.create_cart()
    response.headers["Location"] = f"/cart/{cart_id}"
    return CartCreated(id=cart_id)


@app.get("/cart", tags=["cart"])
async def list_carts(
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: PriceFilter = None,
    max_price: PriceFilter = None,
    min_quantity: QuantityFilter = None,
    max_quantity: QuantityFilter = None,
) -> list[Cart]:
    carts = []
    for cart_id in store.carts:
        cart = store.get_cart(cart_id)
        quantity = sum(item.quantity for item in cart.items)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        carts.append(cart)
    return carts[offset : offset + limit]


@app.get("/cart/{cart_id}", tags=["cart"])
async def get_cart(cart_id: int) -> Cart:
    require_cart(cart_id)
    return store.get_cart(cart_id)


@app.post("/cart/{cart_id}/add/{item_id}", tags=["cart"])
async def add_to_cart(cart_id: int, item_id: int) -> Cart:
    require_cart(cart_id)
    require_item(item_id)
    return store.add_to_cart(cart_id, item_id)


@app.post("/item", status_code=HTTPStatus.CREATED, tags=["item"])
async def create_item(data: ItemData, response: Response) -> Item:
    item = store.create_item(data)
    response.headers["Location"] = f"/item/{item.id}"
    return item


@app.get("/item", tags=["item"])
async def list_items(
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: PriceFilter = None,
    max_price: PriceFilter = None,
    show_deleted: bool = False,
) -> list[Item]:
    items = [
        item
        for item in store.items.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return items[offset : offset + limit]


@app.get("/item/{item_id}", tags=["item"])
async def get_item(item_id: int) -> Item:
    return require_item(item_id)


@app.put("/item/{item_id}", tags=["item"])
async def replace_item(item_id: int, data: ItemData) -> Item:
    require_item(item_id, include_deleted=True)
    return store.replace_item(item_id, data)


@app.patch(
    "/item/{item_id}",
    tags=["item"],
    response_model=Item,
    responses={304: {"description": "Item is deleted"}},
)
async def patch_item(item_id: int, data: ItemPatch) -> Item | Response:
    item = require_item(item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    return store.patch_item(item_id, data)


@app.delete("/item/{item_id}", tags=["item"])
async def delete_item(item_id: int) -> Response:
    item = require_item(item_id, include_deleted=True)
    item.deleted = True
    return Response(status_code=HTTPStatus.OK)


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    username = f"user-{uuid4().hex}"
    await chat_rooms.connect(chat_name, websocket)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            text = message.get("text")
            if text is None:
                await websocket.close(code=1003, reason="Only text messages are supported")
                break
            await chat_rooms.broadcast(chat_name, websocket, f"{username} :: {text}")
    except WebSocketDisconnect:
        pass
    finally:
        chat_rooms.disconnect(chat_name, websocket)
