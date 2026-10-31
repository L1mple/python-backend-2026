from prometheus_fastapi_instrumentator import Instrumentator
from http import HTTPStatus
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Query, Path, Depends, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ConfigDict
from shop_api.database import engine, get_db, Base
from sqlalchemy.orm import Session
from shop_api import models
import uuid

app = FastAPI(title="Shop API")

class ItemCreate(BaseModel):
    name: str
    price: float = Field(gt=0, description="Цена должна быть больше 0")

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    model_config = ConfigDict(extra="forbid")

class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False
    model_config = ConfigDict(from_attributes=True)

def get_item_or_404(db: Session, item_id: int) -> models.Item:
    item = db.query(models.Item).filter(models.Item.id == item_id, models.Item.deleted == False).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.post("/item", status_code=HTTPStatus.CREATED, response_model=ItemResponse)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    new_item = models.Item(name=item.name, price=item.price)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@app.get("/item/{item_id}", response_model=ItemResponse)
def get_item(item_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    return get_item_or_404(db, item_id)

@app.get("/item", response_model=list[ItemResponse])
def list_items(
        offset: int = Query(0, ge=0),
        limit: int = Query(10, ge=1),
        min_price: Optional[float] = Query(None, ge=0),
        max_price: Optional[float] = Query(None, ge=0),
        show_deleted: bool = Query(False),
        db: Session = Depends(get_db)
):
    query = db.query(models.Item)
    if not show_deleted:
        query = query.filter(models.Item.deleted == False)
    if min_price is not None:
        query = query.filter(models.Item.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Item.price <= max_price)

    return query.order_by(models.Item.id).offset(offset).limit(limit).all()

@app.put("/item/{item_id}", response_model=ItemResponse)
def replace_item(item_id: int = Path(..., ge=1), item: ItemCreate = None, db: Session = Depends(get_db)):
    db_item = get_item_or_404(db, item_id)
    db_item.name = item.name
    db_item.price = item.price
    db.commit()
    db.refresh(db_item)
    return db_item

@app.patch("/item/{item_id}", response_model=ItemResponse)
def update_item(item_id: int = Path(..., ge=1), item: ItemUpdate = None, db: Session = Depends(get_db)):
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    if db_item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    update_data = item.model_dump(exclude_unset=True)
    if "deleted" in update_data:
        raise HTTPException(status_code=422, detail="Cannot update 'deleted' field")

    for key, value in update_data.items():
        setattr(db_item, key, value)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.delete("/item/{item_id}")
def delete_item(item_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    db_item.deleted = True
    db.commit()
    return {"status": "ok"}

@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response, db: Session = Depends(get_db)):
    new_cart = models.Cart()
    db.add(new_cart)
    db.commit()
    db.refresh(new_cart)
    response.headers["location"] = f"/cart/{new_cart.id}"
    return {"id": new_cart.id}

@app.get("/cart/{cart_id}")
def get_cart(cart_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    cart = db.query(models.Cart).filter(models.Cart.id == cart_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    items_list = []
    total_price = 0.0
    for ci in cart.items:
        items_list.append({
        "id": ci.item.id,
            "name": ci.item.name,
            "quantity": ci.quantity,
            "available": not ci.item.deleted
        })
        total_price += ci.item.price * ci.quantity

    return {"id": cart.id, "items": items_list, "price": total_price}

@app.get("/cart")
def list_carts(
        offset: int = Query(0, ge=0),
        limit: int = Query(10, ge=1),
        min_price: Optional[float] = Query(None, ge=0),
        max_price: Optional[float] = Query(None, ge=0),
        min_quantity: Optional[int] = Query(None, ge=0),
        max_quantity: Optional[int] = Query(None, ge=0),
        db: Session = Depends(get_db)
):
    carts = db.query(models.Cart).order_by(models.Cart.id).all()
    result = []
    for cart in carts:
        total_price = 0.0
        total_qty = 0
        for ci in cart.items:
            total_price += ci.item.price * ci.quantity
            total_qty += ci.quantity

        if min_price is not None and total_price < min_price: continue
        if max_price is not None and total_price > max_price: continue
        if min_quantity is not None and total_qty < min_quantity: continue
        if max_quantity is not None and total_qty > max_quantity: continue

        items_list = [
            {"id": ci.item.id, "name": ci.item.name, "quantity": ci.quantity, "available": not ci.item.deleted} for ci
            in cart.items]
        result.append({"id": cart.id, "items": items_list, "price": total_price})

    return result[offset:offset + limit]

@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int = Path(..., ge=1), item_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    cart = db.query(models.Cart).filter(models.Cart.id == cart_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    item = get_item_or_404(db, item_id)

    cart_item = db.query(models.CartItem).filter(
        models.CartItem.cart_id == cart_id,
        models.CartItem.item_id == item_id
    ).first()

    if cart_item:
        cart_item.quantity += 1
    else:
        new_ci = models.CartItem(cart_id=cart_id, item_id=item_id, quantity=1)
        db.add(new_ci)

    db.commit()
    return {"status": "ok"}


active_connections: dict[str, list[WebSocket]] = {}

@app.websocket("/chat/{chat_name}")
async def websocket_endpoint(websocket: WebSocket, chat_name: str):
    await websocket.accept()

    if chat_name not in active_connections:
        active_connections[chat_name] = []

    active_connections[chat_name].append(websocket)
    username = f"user_{uuid.uuid4().hex[:4]}"

    try:
        while True:
            data = await websocket.receive_text()
            broadcast_message = f"{username} :: {data}"
            for connection in active_connections[chat_name]:
                await connection.send_text(broadcast_message)

    except WebSocketDisconnect:
        active_connections[chat_name].remove(websocket)
        if not active_connections[chat_name]:
            del active_connections[chat_name]

Instrumentator().instrument(app).expose(app)