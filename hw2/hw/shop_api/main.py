from typing import Annotated

from fastapi import FastAPI, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .chat import Chat
from .errors import CartTotalOverflowError, ResourceNotFoundError
from .models import Cart, Item, ItemInput, ItemPatch
from .store import Shop

app = FastAPI(title="Shop API")
shop = Shop()
chat = Chat()


@app.exception_handler(ResourceNotFoundError)
async def resource_not_found(request, error: ResourceNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(CartTotalOverflowError)
async def cart_total_overflow(request, error: CartTotalOverflowError):
    return JSONResponse(status_code=422, content={"detail": str(error)})


Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(gt=0)]
Price = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]
Quantity = Annotated[int | None, Query(ge=0)]


@app.post("/cart", status_code=201)
async def create_cart(response: Response):
    cart_id = shop.create_cart()
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}", response_model=Cart)
async def get_cart(cart_id: int):
    return shop.get_cart(cart_id)


@app.get("/cart", response_model=list[Cart])
async def list_carts(
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: Price = None,
    max_price: Price = None,
    min_quantity: Quantity = None,
    max_quantity: Quantity = None,
):
    return shop.list_carts(
        offset, limit, min_price, max_price, min_quantity, max_quantity
    )


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
async def add_item(cart_id: int, item_id: int):
    return shop.add_item(cart_id, item_id)


@app.post("/item", status_code=201, response_model=Item)
async def create_item(data: ItemInput, response: Response):
    item = shop.create_item(data)
    response.headers["Location"] = f"/item/{item.id}"
    return item


@app.get("/item/{item_id}", response_model=Item)
async def get_item(item_id: int):
    return shop.get_item(item_id)


@app.get("/item", response_model=list[Item])
async def list_items(
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: Price = None,
    max_price: Price = None,
    show_deleted: bool = False,
):
    return shop.list_items(offset, limit, min_price, max_price, show_deleted)


@app.put("/item/{item_id}", response_model=Item)
async def replace_item(item_id: int, data: ItemInput):
    return shop.replace_item(item_id, data)


@app.patch("/item/{item_id}", response_model=Item)
async def patch_item(item_id: int, data: ItemPatch):
    item = shop.patch_item(item_id, data)
    if item is None:
        return Response(status_code=304)
    return item


@app.delete("/item/{item_id}")
async def delete_item(item_id: int):
    shop.delete_item(item_id)
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
