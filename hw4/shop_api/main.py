from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from shop_api.db import Base, engine, get_db
from shop_api.models import Cart, CartItem, Item


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)
Base.metadata.create_all(bind=engine)

chat_connections: dict[str, list[WebSocket]] = {}


class ItemCreate(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)


class ItemUpdate(ItemCreate):
    pass


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1)
    price: Optional[float] = Field(default=None, gt=0)


class ItemResponse(ItemCreate):
    id: int
    deleted: bool = False


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float


def get_item_or_404(db: Session, item_id: int, *, include_deleted: bool = False) -> Item:
    item = db.get(Item, item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


def get_cart_or_404(db: Session, cart_id: int) -> Cart:
    cart = db.scalar(
        select(Cart)
        .options(selectinload(Cart.items).joinedload(CartItem.item))
        .where(Cart.id == cart_id)
    )
    if cart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    return cart


def item_response(item: Item) -> ItemResponse:
    return ItemResponse(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


def cart_response(cart: Cart) -> CartResponse:
    cart_items: list[CartItemResponse] = []
    total_price = 0.0
    for cart_item in cart.items:
        item = cart_item.item
        cart_items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=cart_item.quantity,
                available=not item.deleted,
            )
        )
        total_price += item.price * cart_item.quantity
    return CartResponse(id=cart.id, items=cart_items, price=total_price)


@app.post("/cart", status_code=status.HTTP_201_CREATED)
def create_cart(response: Response, db: Session = Depends(get_db)) -> dict[str, int]:
    cart = Cart()
    db.add(cart)
    db.flush()
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}", response_model=CartResponse)
def get_cart(cart_id: int, db: Session = Depends(get_db)) -> CartResponse:
    return cart_response(get_cart_or_404(db, cart_id))


@app.get("/cart", response_model=list[CartResponse])
def list_carts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    min_quantity: Optional[int] = Query(default=None, ge=0),
    max_quantity: Optional[int] = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> list[CartResponse]:
    carts = db.scalars(select(Cart).options(selectinload(Cart.items).joinedload(CartItem.item))).all()
    result = [cart_response(cart) for cart in carts]
    if min_price is not None:
        result = [cart for cart in result if cart.price >= min_price]
    if max_price is not None:
        result = [cart for cart in result if cart.price <= max_price]
    if min_quantity is not None:
        result = [cart for cart in result if sum(item.quantity for item in cart.items) >= min_quantity]
    if max_quantity is not None:
        result = [cart for cart in result if sum(item.quantity for item in cart.items) <= max_quantity]
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}", response_model=CartResponse)
def add_item_to_cart(cart_id: int, item_id: int, db: Session = Depends(get_db)) -> CartResponse:
    cart = get_cart_or_404(db, cart_id)
    item = get_item_or_404(db, item_id)
    cart_item = next((row for row in cart.items if row.item_id == item_id), None)
    if cart_item is None:
        cart.items.append(CartItem(item_id=item.id, quantity=1, item=item))
    else:
        cart_item.quantity += 1
    db.flush()
    return cart_response(cart)


@app.post("/item", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, response: Response, db: Session = Depends(get_db)) -> ItemResponse:
    item = Item(name=payload.name, price=payload.price, deleted=False)
    db.add(item)
    db.flush()
    response.headers["Location"] = f"/item/{item.id}"
    return item_response(item)


@app.get("/item/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)) -> ItemResponse:
    return item_response(get_item_or_404(db, item_id))


@app.get("/item", response_model=list[ItemResponse])
def list_items(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    show_deleted: bool = False,
    db: Session = Depends(get_db),
) -> list[ItemResponse]:
    query = select(Item)
    if not show_deleted:
        query = query.where(Item.deleted.is_(False))
    if min_price is not None:
        query = query.where(Item.price >= min_price)
    if max_price is not None:
        query = query.where(Item.price <= max_price)
    items = db.scalars(query.offset(offset).limit(limit)).all()
    return [item_response(item) for item in items]


@app.put("/item/{item_id}", response_model=ItemResponse)
def replace_item(item_id: int, payload: ItemUpdate, db: Session = Depends(get_db)) -> ItemResponse:
    item = get_item_or_404(db, item_id)
    item.name, item.price = payload.name, payload.price
    return item_response(item)


@app.patch("/item/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, payload: ItemPatch, db: Session = Depends(get_db)):
    item = get_item_or_404(db, item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        item.name = changes["name"]
    if "price" in changes:
        item.price = changes["price"]
    return item_response(item)


@app.delete("/item/{item_id}", status_code=status.HTTP_200_OK)
def delete_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    item = get_item_or_404(db, item_id, include_deleted=True)
    item.deleted = True
    return {"id": item.id}


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()
    username = uuid4().hex[:8]
    members = chat_connections.setdefault(chat_name, [])
    members.append(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            for member in members.copy():
                if member is not websocket:
                    await member.send_text(f"{username} :: {message}")
    except WebSocketDisconnect:
        pass
    finally:
        members.remove(websocket)
        if not members:
            del chat_connections[chat_name]
