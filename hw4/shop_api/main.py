from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from shop_api.db import Base, CartItemORM, CartORM, ItemORM, engine, get_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)

class ItemBase(BaseModel):
    name: str
    price: float


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    price: Optional[float] = None
    deleted: Optional[bool] = None


class Item(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deleted: bool = False


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: List[CartItem]
    price: float


class CartIdResponse(BaseModel):
    id: int


ITEM_NOT_FOUND = "Item not found"
CART_NOT_FOUND = "Cart not found"


def cart_to_schema(cart: CartORM) -> Cart:
    items = [
        CartItem(
            id=ci.item_id,
            name=ci.item.name,
            quantity=ci.quantity,
            available=not ci.item.deleted,
        )
        for ci in cart.items
    ]
    price = sum(ci.item.price * ci.quantity for ci in cart.items)
    return Cart(id=cart.id, items=items, price=price)


def load_cart(db: Session, cart_id: int) -> Optional[CartORM]:
    return db.scalar(
        select(CartORM)
        .where(CartORM.id == cart_id)
        .execution_options(populate_existing=True)
    )


@app.post("/item", response_model=Item, status_code=201)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    obj = ItemORM(name=item.name, price=item.price, deleted=False)
    db.add(obj)
    db.commit()
    return Item.model_validate(obj)


@app.get("/item/{item_id}", response_model=Item)
def get_item(item_id: int, db: Session = Depends(get_db)):
    obj = db.get(ItemORM, item_id)
    if obj is None or obj.deleted:
        raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
    return Item.model_validate(obj)


@app.get("/item", response_model=List[Item])
def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(ItemORM)
    if not show_deleted:
        stmt = stmt.where(ItemORM.deleted.is_(False))
    if min_price is not None:
        stmt = stmt.where(ItemORM.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(ItemORM.price <= max_price)
    stmt = stmt.order_by(ItemORM.id).offset(offset).limit(limit)
    return [Item.model_validate(o) for o in db.scalars(stmt)]


@app.put("/item/{item_id}", response_model=Item)
def update_item(item_id: int, item: ItemCreate, db: Session = Depends(get_db)):
    obj = db.get(ItemORM, item_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
    obj.name = item.name
    obj.price = item.price
    obj.deleted = False
    db.commit()
    return Item.model_validate(obj)


@app.patch("/item/{item_id}", response_model=Item)
def patch_item(item_id: int, item: ItemUpdate, db: Session = Depends(get_db)):
    obj = db.get(ItemORM, item_id)
    if obj is None or obj.deleted:
        raise HTTPException(status_code=304, detail="Not modified")
    if item.deleted is not None:
        raise HTTPException(
            status_code=422, detail="Cannot update 'deleted' field via PATCH"
        )
    if item.name is not None:
        obj.name = item.name
    if item.price is not None:
        obj.price = item.price
    db.commit()
    return Item.model_validate(obj)


@app.delete("/item/{item_id}", response_model=Item)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    obj = db.get(ItemORM, item_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
    obj.deleted = True
    db.commit()
    return Item.model_validate(obj)


@app.post("/cart", response_model=CartIdResponse, status_code=201)
def create_cart(response: Response, db: Session = Depends(get_db)):
    cart = CartORM()
    db.add(cart)
    db.commit()
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}", response_model=Cart)
def get_cart(cart_id: int, db: Session = Depends(get_db)):
    cart = load_cart(db, cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail=CART_NOT_FOUND)
    return cart_to_schema(cart)


@app.get("/cart", response_model=List[Cart])
def list_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    total_price = func.coalesce(func.sum(ItemORM.price * CartItemORM.quantity), 0.0)
    total_qty = func.coalesce(func.sum(CartItemORM.quantity), 0)
    stmt = (
        select(CartORM.id)
        .outerjoin(CartItemORM, CartItemORM.cart_id == CartORM.id)
        .outerjoin(ItemORM, ItemORM.id == CartItemORM.item_id)
        .group_by(CartORM.id)
    )
    if min_price is not None:
        stmt = stmt.having(total_price >= min_price)
    if max_price is not None:
        stmt = stmt.having(total_price <= max_price)
    if min_quantity is not None:
        stmt = stmt.having(total_qty >= min_quantity)
    if max_quantity is not None:
        stmt = stmt.having(total_qty <= max_quantity)
    stmt = stmt.order_by(CartORM.id).offset(offset).limit(limit)

    cart_ids = list(db.scalars(stmt))
    if not cart_ids:
        return []

    carts = db.scalars(
        select(CartORM)
        .where(CartORM.id.in_(cart_ids))
        .order_by(CartORM.id)
        .execution_options(populate_existing=True)
    )
    return [cart_to_schema(c) for c in carts]


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
def add_to_cart(cart_id: int, item_id: int, db: Session = Depends(get_db)):
    if db.scalar(select(CartORM.id).where(CartORM.id == cart_id)) is None:
        raise HTTPException(status_code=404, detail=CART_NOT_FOUND)
    if db.scalar(select(ItemORM.id).where(ItemORM.id == item_id)) is None:
        raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
    stmt = pg_insert(CartItemORM).values(cart_id=cart_id, item_id=item_id, quantity=1)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_cart_item",
        set_={"quantity": CartItemORM.quantity + 1},
    )
    db.execute(stmt)
    db.commit()

    return cart_to_schema(load_cart(db, cart_id))