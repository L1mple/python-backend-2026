
from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from .models import NewItem, Item, UpdateItem, Cart, CartItem
from uuid import uuid4


app = FastAPI(title="Shop API")

items = {}
carts = {}

next_id = 1
next_cart_id = 1

@app.post("/item",status_code=201)
async def create_item(new_item: NewItem):
    global next_id
    item = Item(
        id=next_id,
        name=new_item.name,
        price=new_item.price,
        deleted= False,
    )
    items[next_id] = item
    next_id = next_id + 1
    return item

@app.get("/item/{item_id}")
async def get_item(item_id: int):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")

    item = items[item_id]

    if item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")

    return item

@app.delete("/item/{item_id}")
async def delete_item(item_id: int):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    item = items[item_id]

    item.deleted = True

    for cart in carts.values():
        for cart_item in cart.items:
            if cart_item.id == item_id:
                cart_item.available = False

    return item

@app.put("/item/{item_id}")
async def update_item(item_id: int, new_item: NewItem):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    item = items[item_id]
    if item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    item.name = new_item.name
    item.price = new_item.price
    return item

@app.patch("/item/{item_id}")
async def patch_item(item_id: int, up_item: UpdateItem):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    item = items[item_id]
    if item.deleted:
        raise HTTPException(status_code=304, detail="Item not found")
    if up_item.name != None:
        item.name = up_item.name
    if up_item.price != None:
        item.price = up_item.price
    return item


@app.get("/item")
async def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
):
    result = list(items.values())

    if not show_deleted:
        result = [item for item in result if not item.deleted]

    if min_price != None:
        result = [item for item in result if not item.price < min_price]

    if max_price != None:
        result = [item for item in result if not item.price > max_price]

    result = result[offset:offset+limit]

    return result

@app.post("/cart", status_code=201)
async def create_cart(response: Response):
    global next_cart_id

    cart = Cart(
        id=next_cart_id,
        items=[],
        price = 0.0,
    )

    carts[next_cart_id] = cart
    next_cart_id = next_cart_id + 1

    response.headers["Location"] = f"/cart/{cart.id}"

    return {"id": cart.id}

@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int):
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    cart = carts[cart_id]

    cart.price = sum(
        items[cart_item.id].price * cart_item.quantity
        for cart_item in cart.items
    )

    return cart

@app.get("/cart")
async def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
):
    result = list(carts.values())

    if min_price != None:
        result = [cart for cart in result if not cart.price < min_price]

    if max_price != None:
        result = [cart for cart in result if not cart.price > max_price]

    if min_quantity != None:
        result = [cart for cart in result if not sum(item.quantity for item in cart.items) < min_quantity]

    if max_quantity != None:
        result = [cart for cart in result if not sum(item.quantity for item in cart.items) > max_quantity]

    for cart in result:
        cart.price = sum(
            items[cart_item.id].price * cart_item.quantity
            for cart_item in cart.items
        )

    result = result[offset:offset+limit]

    return result

@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int):
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    item = items[item_id]
    if item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    cart = carts[cart_id]

    for cart_item in cart.items:
        if cart_item.id == item_id:
            cart_item.quantity += 1
            cart.price += item.price
            return cart

    cart_item = CartItem(
        id = item_id,
        name = item.name,
        quantity = 1,
        available = True,

    )
    cart.items.append(cart_item)
    cart.price += item.price

    return cart


# ДОП ЗАДАНИЕ

rooms ={}
@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str):
    await websocket.accept()

    username = uuid4().hex

    if chat_name not in rooms:
        rooms[chat_name] = []

    rooms[chat_name].append(websocket)

    try:
        while True:
            message = await websocket.receive_text()

            for client in rooms[chat_name]:
                if client != websocket:
                    await client.send_text(f"{username} :: {message}")
    except WebSocketDisconnect:
        rooms[chat_name].remove(websocket)

        if not rooms[chat_name]:
            del rooms[chat_name]




