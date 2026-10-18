
from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect, Depends
from .models import NewItem, Item, UpdateItem, Cart, CartItem
from .dbase import Base, engine, get_db
from .db_models import ItemDB, CartDB, CartItemDB
from uuid import uuid4

from prometheus_fastapi_instrumentator import Instrumentator

from sqlalchemy.orm import Session



app = FastAPI(title="Shop API")

Instrumentator().instrument(app).expose(app)

Base.metadata.create_all(bind=engine)


@app.post("/item", status_code=201)
def create_item(new_item: NewItem, db: Session = Depends(get_db)):
    item = ItemDB(
        name=new_item.name,
        price=new_item.price,
        deleted=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@app.get("/item/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ItemDB, item_id)

    if item is None or item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.delete("/item/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ItemDB, item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    item.deleted = True
    db.commit()
    return item

@app.put("/item/{item_id}")
def update_item(item_id: int, new_item: NewItem, db: Session = Depends(get_db)):
    item = db.get(ItemDB, item_id)

    if item is None or item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")

    item.name = new_item.name
    item.price = new_item.price
    db.commit()
    return item

@app.patch("/item/{item_id}")
def patch_item(item_id: int, up_item: UpdateItem, db: Session = Depends(get_db)):
    item = db.get(ItemDB, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.deleted:
        raise HTTPException(status_code=304)
    if up_item.name != None:
        item.name = up_item.name
    if up_item.price != None:
        item.price = up_item.price
    db.commit()
    return item


@app.get("/item")
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
    db: Session = Depends(get_db),
):
    result = db.query(ItemDB).order_by(ItemDB.id).all()
    if not show_deleted:
        result = [item for item in result if not item.deleted]
    if min_price != None:
        result = [item for item in result if not item.price < min_price]
    if max_price != None:
        result = [item for item in result if not item.price > max_price]
    result = result[offset:offset+limit]

    return result


def make_cart(db, cart):
    cart_items = db.query(CartItemDB).filter_by(cart_id=cart.id).all()
    result = []
    price = 0
    for cart_item in cart_items:
        item = db.get(ItemDB, cart_item.item_id)
        result.append({
            "id": item.id,
            "name": item.name,
            "quantity": cart_item.quantity,
            "available": not item.deleted,
        })
        price += item.price * cart_item.quantity

    return {"id": cart.id, "items": result, "price": price}

@app.post("/cart", status_code=201)
def create_cart(response: Response, db: Session = Depends(get_db)):
    cart = CartDB()
    db.add(cart)
    db.commit()
    db.refresh(cart)

    response.headers["Location"] = f"/cart/{cart.id}"

    return {"id": cart.id}

@app.get("/cart/{cart_id}")
def get_cart(cart_id: int, db: Session = Depends(get_db)):
    cart = db.get(CartDB, cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")

    return make_cart(db, cart)

@app.get("/cart")
def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    carts = db.query(CartDB).order_by(CartDB.id).all()
    result = [make_cart(db, cart) for cart in carts]

    if min_price != None:
        result = [cart for cart in result if cart["price"] >= min_price]
    if max_price != None:
        result = [cart for cart in result if cart["price"] <= max_price]
    if min_quantity != None:
        result = [
            cart for cart in result
            if sum(item["quantity"] for item in cart["items"]) >= min_quantity
        ]
    if max_quantity != None:
        result = [
            cart for cart in result
            if sum(item["quantity"] for item in cart["items"]) <= max_quantity
        ]

    return result[offset:offset+limit]

@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int, db: Session = Depends(get_db)):
    cart = db.get(CartDB, cart_id)
    item = db.get(ItemDB, item_id)

    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    if item is None or item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")

    cart_item = db.get(CartItemDB, (cart_id, item_id))

    if cart_item is not None:
        cart_item.quantity += 1
    else:
        cart_item = CartItemDB(
            cart_id=cart_id,
            item_id=item_id,
            quantity=1,
        )
        db.add(cart_item)


    db.commit()
    return make_cart(db, cart)


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




