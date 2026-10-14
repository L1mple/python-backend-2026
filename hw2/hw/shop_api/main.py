"""REST/RPC shop API and a WebSocket chat with separate rooms."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import database
from .chat import ChatRooms
from .database import ItemRecord, get_session
from .models import Cart, CartCreated, Item, ItemData, ItemPatch
from .store import ShopStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await run_in_threadpool(database.Base.metadata.create_all, database.engine)
    try:
        yield
    finally:
        await run_in_threadpool(database.engine.dispose)


app = FastAPI(title="Shop API", lifespan=lifespan)
Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["^/metrics$", "^/docs$", "^/redoc$", "^/openapi.json$"],
).add(
    metrics.default(
        latency_highr_buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10),
    )
).instrument(app).expose(app, include_in_schema=False)
chat_rooms = ChatRooms()


def get_store(session: Annotated[Session, Depends(get_session, scope="function")]) -> ShopStore:
    return ShopStore(session)


Store = Annotated[ShopStore, Depends(get_store)]

Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(gt=0)]
PriceFilter = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]
QuantityFilter = Annotated[int | None, Query(ge=0)]


def require_item(
    store: ShopStore, item_id: int, *, include_deleted: bool = False, lock: bool = False
) -> ItemRecord:
    item = store.get_item(item_id, lock=lock)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


def require_cart(store: ShopStore, cart_id: int, *, lock: bool = False) -> None:
    if store.get_cart_record(cart_id, lock=lock) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")


@app.post("/cart", status_code=HTTPStatus.CREATED, tags=["cart"])
def create_cart(response: Response, store: Store) -> CartCreated:
    cart_id = store.create_cart()
    response.headers["Location"] = f"/cart/{cart_id}"
    return CartCreated(id=cart_id)


@app.get("/cart", tags=["cart"])
def list_carts(
    store: Store,
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: PriceFilter = None,
    max_price: PriceFilter = None,
    min_quantity: QuantityFilter = None,
    max_quantity: QuantityFilter = None,
) -> list[Cart]:
    carts = []
    for cart_id in store.cart_ids():
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
def get_cart(cart_id: int, store: Store) -> Cart:
    require_cart(store, cart_id)
    return store.get_cart(cart_id)


@app.post("/cart/{cart_id}/add/{item_id}", tags=["cart"])
def add_to_cart(cart_id: int, item_id: int, store: Store) -> Cart:
    require_cart(store, cart_id, lock=True)
    require_item(store, item_id, lock=True)
    return store.add_to_cart(cart_id, item_id)


@app.post("/item", status_code=HTTPStatus.CREATED, tags=["item"])
def create_item(data: ItemData, response: Response, store: Store) -> Item:
    item = store.create_item(data)
    response.headers["Location"] = f"/item/{item.id}"
    return item


@app.get("/item", tags=["item"])
def list_items(
    store: Store,
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: PriceFilter = None,
    max_price: PriceFilter = None,
    show_deleted: bool = False,
) -> list[Item]:
    return store.list_items(offset, limit, min_price, max_price, show_deleted)


@app.get("/item/{item_id}", tags=["item"])
def get_item(item_id: int, store: Store) -> Item:
    return Item.model_validate(require_item(store, item_id), from_attributes=True)


@app.put("/item/{item_id}", tags=["item"])
def replace_item(item_id: int, data: ItemData, store: Store) -> Item:
    item = require_item(store, item_id, include_deleted=True, lock=True)
    return store.replace_item(item, data)


@app.patch(
    "/item/{item_id}",
    tags=["item"],
    response_model=Item,
    responses={304: {"description": "Item is deleted"}},
)
def patch_item(item_id: int, data: ItemPatch, store: Store) -> Item | Response:
    item = require_item(store, item_id, include_deleted=True, lock=True)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    return store.patch_item(item, data)


@app.delete("/item/{item_id}", tags=["item"])
def delete_item(item_id: int, store: Store) -> Response:
    item = require_item(store, item_id, include_deleted=True, lock=True)
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
