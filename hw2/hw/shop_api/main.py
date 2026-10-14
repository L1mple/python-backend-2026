from http import HTTPStatus
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="Shop API")

items: dict[int, dict] = {}
carts: dict[int, dict] = {}
chats: dict[str, list[WebSocket]] = {}


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None


def item_view(item: dict) -> dict:
    return {
        "id": item["id"],
        "name": item["name"],
        "price": item["price"],
        "deleted": item["deleted"],
    }


def cart_view(cart: dict) -> dict:
    lines = []
    price = 0.0
    for item_id, quantity in cart["items"].items():
        item = items[item_id]
        lines.append({
            "id": item_id,
            "name": item["name"],
            "quantity": quantity,
            "available": not item["deleted"],
        })
        price += item["price"] * quantity
    return {"id": cart["id"], "items": lines, "price": price}


def cart_quantity(cart: dict) -> int:
    return sum(cart["items"].values())


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response) -> dict:
    cart_id = max(carts, default=0) + 1
    carts[cart_id] = {"id": cart_id, "items": {}}
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> dict:
    cart = carts.get(cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "cart not found")
    return cart_view(cart)


@app.get("/cart")
def get_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[dict]:
    result = []
    for cart in carts.values():
        view = cart_view(cart)
        quantity = cart_quantity(cart)
        if min_price is not None and view["price"] < min_price:
            continue
        if max_price is not None and view["price"] > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(view)
    return result[offset:offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int) -> dict:
    cart = carts.get(cart_id)
    item = items.get(item_id)
    if cart is None or item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "not found")

    cart["items"][item_id] = cart["items"].get(item_id, 0) + 1
    return cart_view(cart)


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(body: ItemIn, response: Response) -> dict:
    item_id = max(items, default=0) + 1
    item = {
        "id": item_id,
        "name": body.name,
        "price": body.price,
        "deleted": False,
    }
    items[item_id] = item
    response.headers["location"] = f"/item/{item_id}"
    return item_view(item)


@app.get("/item/{item_id}")
def get_item(item_id: int) -> dict:
    item = items.get(item_id)
    if item is None or item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_FOUND, "item not found")
    return item_view(item)


@app.get("/item")
def get_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[dict]:
    result = []
    for item in items.values():
        if item["deleted"] and not show_deleted:
            continue
        if min_price is not None and item["price"] < min_price:
            continue
        if max_price is not None and item["price"] > max_price:
            continue
        result.append(item_view(item))
    return result[offset:offset + limit]


@app.put("/item/{item_id}")
def put_item(item_id: int, body: ItemIn) -> dict:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "item not found")

    item["name"] = body.name
    item["price"] = body.price
    return item_view(item)


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatch):
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "item not found")
    if item["deleted"]:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    if body.name is not None:
        item["name"] = body.name
    if body.price is not None:
        item["price"] = body.price
    return item_view(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> dict:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "item not found")

    item["deleted"] = True
    return item_view(item)


@app.websocket("/chat/{chat_name}")
async def chat(ws: WebSocket, chat_name: str) -> None:
    await ws.accept()
    username = f"user-{uuid4().hex[:6]}"
    chats.setdefault(chat_name, []).append(ws)
    try:
        while True:
            message = await ws.receive_text()
            text = f"{username} :: {message}"
            for client in list(chats.get(chat_name, [])):
                if client is not ws:
                    await client.send_text(text)
    except WebSocketDisconnect:
        room = chats.get(chat_name, [])
        if ws in room:
            room.remove(ws)
