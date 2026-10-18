from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Cart, CartLine, Item


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


# Tables are initialized here as well so the supplied TestClient(app) tests,
# which do not use the context manager, work without additional fixtures.
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Shop API", lifespan=lifespan)
Db = Annotated[Session, Depends(get_db)]


class ItemCreate(BaseModel):
    name: str
    price: float = Field(ge=0)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    price: float | None = Field(default=None, ge=0)


def serialize_item(item: Item) -> dict:
    return {"id": item.id, "name": item.name, "price": item.price, "deleted": item.deleted}


def get_item_or_404(db: Session, item_id: int, *, include_deleted: bool = False) -> Item:
    item = db.get(Item, item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def get_cart_or_404(db: Session, cart_id: int) -> Cart:
    cart = db.get(Cart, cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


def serialize_cart(cart: Cart) -> dict:
    lines = sorted(cart.lines, key=lambda x: x.item_id)
    entries = [
        {"id": line.item_id, "name": line.item.name, "quantity": line.quantity,
         "available": not line.item.deleted}
        for line in lines
    ]
    return {"id": cart.id, "items": entries,
            "price": sum(line.item.price * line.quantity for line in lines)}


@app.post("/item", status_code=201)
def create_item(payload: ItemCreate, response: Response, db: Db):
    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    response.headers["Location"] = f"/item/{item.id}"
    return serialize_item(item)


@app.get("/item")
def list_items(db: Db, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1),
               min_price: float = Query(0, ge=0), max_price: float | None = Query(None, ge=0),
               show_deleted: bool = False):
    stmt = select(Item).where(Item.price >= min_price)
    if not show_deleted:
        stmt = stmt.where(Item.deleted.is_(False))
    if max_price is not None:
        stmt = stmt.where(Item.price <= max_price)
    return [serialize_item(x) for x in db.scalars(stmt.order_by(Item.id).offset(offset).limit(limit))]


@app.get("/item/{item_id}")
def read_item(item_id: int, db: Db):
    return serialize_item(get_item_or_404(db, item_id))


@app.put("/item/{item_id}")
def replace_item(item_id: int, payload: ItemCreate, db: Db):
    item = get_item_or_404(db, item_id)
    item.name = payload.name
    item.price = payload.price
    db.commit()
    return serialize_item(item)


@app.patch("/item/{item_id}")
def patch_item(item_id: int, payload: ItemPatch, db: Db):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.deleted:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(item, field, value)
    db.commit()
    return serialize_item(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int, db: Db):
    item = db.get(Item, item_id)
    if item:
        item.deleted = True
        db.commit()
    return {"status": "ok"}


@app.post("/cart", status_code=201)
def create_cart(response: Response, db: Db):
    cart = Cart()
    db.add(cart)
    db.commit()
    db.refresh(cart)
    response.headers["Location"] = f"/cart/{cart.id}"
    return serialize_cart(cart)


@app.get("/cart/{cart_id}")
def read_cart(cart_id: int, db: Db):
    return serialize_cart(get_cart_or_404(db, cart_id))


@app.get("/cart")
def list_carts(db: Db, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1),
               min_price: float = Query(0, ge=0), max_price: float | None = Query(None, ge=0),
               min_quantity: int = Query(0, ge=0), max_quantity: int | None = Query(None, ge=0)):
    carts = db.scalars(select(Cart).order_by(Cart.id)).all()
    serialized = [serialize_cart(c) for c in carts]
    serialized = [c for c in serialized if c["price"] >= min_price
                  and (max_price is None or c["price"] <= max_price)
                  and sum(x["quantity"] for x in c["items"]) >= min_quantity
                  and (max_quantity is None or sum(x["quantity"] for x in c["items"]) <= max_quantity)]
    return serialized[offset:offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int, db: Db):
    cart = get_cart_or_404(db, cart_id)
    get_item_or_404(db, item_id)
    line = db.scalar(select(CartLine).where(CartLine.cart_id == cart_id, CartLine.item_id == item_id))
    if line:
        line.quantity += 1
    else:
        db.add(CartLine(cart_id=cart_id, item_id=item_id, quantity=1))
    db.commit()
    db.refresh(cart)
    return serialize_cart(cart)
