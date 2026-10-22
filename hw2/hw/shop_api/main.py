from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from itertools import count

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect

app = FastAPI(title="Shop API")


@dataclass
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass
class Cart:
    id: int
    price: float = 0.0
    items: dict[int, int] = field(default_factory=dict)


items: dict[int, Item] = {}
carts: dict[int, Cart] = {}
item_ids = count(1)
cart_ids = count(1)
user_ids = count(1)
chat_clients: dict[str, set[WebSocket]] = {}


def get_item_or_404(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} was not found")
    return item


def get_cart_or_404(cart_id: int) -> Cart:
    cart = carts.get(cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} was not found")
    return cart


def item_response(item: Item) -> dict[str, object]:
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }


def cart_response(cart: Cart) -> dict[str, object]:
    cart_items: list[dict[str, object]] = []
    for item_id, quantity in cart.items.items():
        item = items[item_id]
        cart_items.append({
            "id": item.id,
            "name": item.name,
            "quantity": quantity,
            "available": not item.deleted,
        })
    return {"id": cart.id, "items": cart_items, "price": cart.price}


def update_cart_prices(item_id: int, price_delta: float) -> None:
    for cart in carts.values():
        cart.price += cart.items.get(item_id, 0) * price_delta


async def get_body(request: Request) -> dict[str, object]:
    try:
        body = await request.json()
    except ValueError as error:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Request body must be a JSON object") from error
    if not isinstance(body, dict):
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Request body must be a JSON object")
    return body


def validate_item_body(body: dict[str, object], partial: bool = False) -> tuple[str | None, float | None]:
    allowed = {"name", "price"}
    if set(body) - allowed or (not partial and set(body) != allowed):
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid item data")

    name = body.get("name")
    price = body.get("price")
    if not partial or "name" in body:
        if not isinstance(name, str):
            raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Item name must be a string")
    if not partial or "price" in body:
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
            raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Item price must be non-negative")
    return name if isinstance(name, str) else None, float(price) if isinstance(price, (int, float)) else None


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response) -> dict[str, object]:
    cart = Cart(next(cart_ids))
    carts[cart.id] = cart
    response.headers["location"] = f"/cart/{cart.id}"
    return cart_response(cart)


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> dict[str, object]:
    return cart_response(get_cart_or_404(cart_id))


@app.get("/cart")
async def get_cart_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
) -> list[dict[str, object]]:
    result = []
    for cart in carts.values():
        cart_data = cart_response(cart) # что такое view
        quantity = sum(item["quantity"] for item in cart_data["items"])
        if min_price is not None and cart_data["price"] < min_price:
            continue
        if max_price is not None and cart_data["price"] > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(cart_data)
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> dict[str, object]:
    cart = get_cart_or_404(cart_id)
    item = get_item_or_404(item_id)
    cart.items[item_id] = cart.items.get(item_id, 0) + 1
    cart.price += item.price
    return cart_response(cart)


@app.post("/item", status_code=HTTPStatus.CREATED)
async def post_item(request: Request, response: Response) -> dict[str, object]:
    body = await get_body(request)
    name, price = validate_item_body(body)
    item = Item(next(item_ids), name or "", price or 0.0)
    items[item.id] = item
    response.headers["location"] = f"/item/{item.id}"
    return item_response(item)


@app.get("/item/{item_id}")
async def get_item(item_id: int) -> dict[str, object]:
    return item_response(get_item_or_404(item_id))


@app.get("/item")
async def get_item_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = Query(False),
) -> list[dict[str, object]]:
    result = [
        item_response(item)
        for item in items.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return result[offset : offset + limit]


@app.put("/item/{item_id}")
async def put_item(item_id: int, request: Request) -> dict[str, object]:
    body = await get_body(request)
    name, price = validate_item_body(body)
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} cannot be replaced")
    old_price = item.price
    item.name = name or ""
    item.price = price or 0.0
    update_cart_prices(item_id, item.price - old_price)
    return item_response(item)


@app.patch("/item/{item_id}")
async def patch_item(item_id: int, request: Request) -> dict[str, object]:
    body = await get_body(request)
    name, price = validate_item_body(body, partial=True)
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} cannot be updated")
    old_price = item.price
    if "name" in body:
        item.name = name or ""
    if "price" in body:
        item.price = price or 0.0
        update_cart_prices(item_id, item.price - old_price)
    return item_response(item)


@app.delete("/item/{item_id}")
async def delete_item(item_id: int) -> Response:
    item = items.get(item_id)
    if item is not None and not item.deleted:
        update_cart_prices(item_id, -item.price)
        item.deleted = True
    return Response(status_code=HTTPStatus.OK)


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()
    clients = chat_clients.setdefault(chat_name, set())
    clients.add(websocket)
    username = f"user-{next(user_ids)}"
    try:
        while True:
            message = await websocket.receive_text()
            for client in tuple(clients):
                if client is not websocket:
                    await client.send_text(f"{username} :: {message}")
    except WebSocketDisconnect:
        clients.discard(websocket)
        if not clients:
            chat_clients.pop(chat_name, None)
