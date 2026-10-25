import random
import string
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Optional

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, ConfigDict
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import CartItemOrm, CartOrm, ItemOrm


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shop API")

Instrumentator().instrument(app).expose(app)

ITEMS_CREATED = Counter("shop_items_created_total", "Number of created items")
CARTS_CREATED = Counter("shop_carts_created_total", "Number of created carts")


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    price: Optional[float] = None


class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    deleted: bool = False


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


def build_cart(db: Session, cart_id: int) -> Cart:
    rows = db.execute(
        select(CartItemOrm.quantity, ItemOrm)
        .join(ItemOrm, ItemOrm.id == CartItemOrm.item_id)
        .where(CartItemOrm.cart_id == cart_id)
        .order_by(ItemOrm.id)
    ).all()

    items: list[CartItem] = []
    total = 0.0

    for quantity, item in rows:
        items.append(
            CartItem(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        total += item.price * quantity

    return Cart(id=cart_id, items=items, price=total)


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response, db: Session = Depends(get_db)) -> dict:
    cart = CartOrm()
    db.add(cart)
    db.commit()
    CARTS_CREATED.inc()
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int, db: Session = Depends(get_db)) -> Cart:
    if db.get(CartOrm, cart_id) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return build_cart(db, cart_id)


@app.get("/cart")
def get_cart_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
    db: Session = Depends(get_db),
) -> list[Cart]:
    result: list[Cart] = []

    for cart_id in db.scalars(select(CartOrm.id).order_by(CartOrm.id)).all():
        cart = build_cart(db, cart_id)
        total_quantity = sum(i.quantity for i in cart.items)

        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int, db: Session = Depends(get_db)) -> Cart:
    if db.get(CartOrm, cart_id) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    if db.get(ItemOrm, item_id) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")

    link = db.get(CartItemOrm, (cart_id, item_id), with_for_update=True)
    if link is None:
        db.add(CartItemOrm(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        link.quantity += 1
    db.commit()
    return build_cart(db, cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(
    body: ItemCreate, response: Response, db: Session = Depends(get_db)
) -> Item:
    item = ItemOrm(name=body.name, price=body.price)
    db.add(item)
    db.commit()
    db.refresh(item)
    ITEMS_CREATED.inc()
    response.headers["location"] = f"/item/{item.id}"
    return Item.model_validate(item)


@app.get("/item/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)) -> Item:
    item = db.get(ItemOrm, item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return Item.model_validate(item)


@app.get("/item")
def get_item_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = False,
    db: Session = Depends(get_db),
) -> list[Item]:
    stmt = select(ItemOrm).order_by(ItemOrm.id)
    if not show_deleted:
        stmt = stmt.where(ItemOrm.deleted.is_(False))
    if min_price is not None:
        stmt = stmt.where(ItemOrm.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(ItemOrm.price <= max_price)

    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return [Item.model_validate(r) for r in rows]


@app.put("/item/{item_id}")
def replace_item(item_id: int, body: ItemCreate, db: Session = Depends(get_db)) -> Item:
    item = db.get(ItemOrm, item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")

    item.name = body.name
    item.price = body.price
    db.commit()
    return Item.model_validate(item)


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatch, db: Session = Depends(get_db)):
    item = db.get(ItemOrm, item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    db.commit()
    return Item.model_validate(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)) -> dict:
    item = db.get(ItemOrm, item_id)
    if item is not None:
        item.deleted = True
        db.commit()
    return {}


@dataclass
class ChatRoom:
    members: dict[WebSocket, str] = field(default_factory=dict)


chat_rooms: dict[str, ChatRoom] = {}


def random_username() -> str:
    return "user_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()

    room = chat_rooms.setdefault(chat_name, ChatRoom())
    username = random_username()
    room.members[websocket] = username

    try:
        while True:
            message = await websocket.receive_text()
            text = f"{username} :: {message}"

            for member in list(room.members):
                if member is not websocket:
                    await member.send_text(text)
    except WebSocketDisconnect:
        pass
    finally:
        room.members.pop(websocket, None)
        if not room.members:
            chat_rooms.pop(chat_name, None)