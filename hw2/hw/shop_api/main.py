from typing import Annotated

from fastapi import FastAPI, Query, Response, WebSocket, WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator

from .chat import Chat
from .models import Cart, Item, ItemInput, ItemPatch
from .metrics import metrics
from .store import Shop

app = FastAPI(title="Shop API")
Instrumentator(excluded_handlers=["/metrics"]).instrument(
    app,
    latency_highr_buckets=(
        0.0001,
        0.00025,
        0.0005,
        0.001,
        0.0025,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2.5,
        5,
        10,
        30,
        60,
    ),
).expose(app)
shop = Shop()
chat = Chat()

Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(gt=0)]
Price = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]
Quantity = Annotated[int | None, Query(ge=0)]


@app.post("/cart", status_code=201)
def create_cart(response: Response):
    with metrics.stage("cart_creation"):
        cart_id = shop.create_cart()
    metrics.created.labels(resource="cart").inc()
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}", response_model=Cart)
def get_cart(cart_id: int):
    with metrics.stage("cart_lookup"):
        cart = shop.get_cart(cart_id)
    metrics.observe_cart(cart)
    return cart


@app.get("/cart", response_model=list[Cart])
def list_carts(
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: Price = None,
    max_price: Price = None,
    min_quantity: Quantity = None,
    max_quantity: Quantity = None,
):
    with metrics.stage("cart_filter"):
        return shop.list_carts(
            offset, limit, min_price, max_price, min_quantity, max_quantity
        )


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
def add_item(cart_id: int, item_id: int):
    with metrics.stage("cart_mutation"):
        cart = shop.add_item(cart_id, item_id)
    metrics.observe_cart(cart)
    return cart


@app.post("/item", status_code=201, response_model=Item)
def create_item(data: ItemInput, response: Response):
    with metrics.stage("item_creation"):
        item = shop.create_item(data)
    metrics.created.labels(resource="item").inc()
    response.headers["Location"] = f"/item/{item.id}"
    return item


@app.get("/item/{item_id}", response_model=Item)
def get_item(item_id: int):
    return shop.get_item(item_id)


@app.get("/item", response_model=list[Item])
def list_items(
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: Price = None,
    max_price: Price = None,
    show_deleted: bool = False,
):
    with metrics.stage("catalog_filter"):
        return shop.list_items(offset, limit, min_price, max_price, show_deleted)


@app.put("/item/{item_id}", response_model=Item)
def replace_item(item_id: int, data: ItemInput):
    with metrics.stage("item_update"):
        return shop.replace_item(item_id, data)


@app.patch("/item/{item_id}", response_model=Item)
def patch_item(item_id: int, data: ItemPatch):
    with metrics.stage("item_update"):
        item = shop.patch_item(item_id, data)
    if item is None:
        return Response(status_code=304)
    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int):
    with metrics.stage("item_deletion"):
        shop.delete_item(item_id)
    metrics.deletions.inc()
    return Response(status_code=200)


@app.websocket("/chat/{chat_name}")
async def websocket_chat(websocket: WebSocket, chat_name: str):
    await chat.connect(chat_name, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await chat.broadcast(chat_name, websocket, message)
    except WebSocketDisconnect:
        pass
    finally:
        chat.disconnect(chat_name, websocket)
