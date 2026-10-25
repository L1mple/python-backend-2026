import os

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///shop.db"))

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class ItemModel(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    price = Column(Float)
    deleted = Column(Boolean, default=False)


class CartModel(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)


class CartItemModel(Base):
    __tablename__ = "cart_items"

    cart_id = Column(Integer, ForeignKey("carts.id"), primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), primary_key=True)
    quantity = Column(Integer)


Base.metadata.create_all(engine)

app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)


class Item(BaseModel):
    name: str
    price: float


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create(db, cid):
    cart = db.get(CartModel, cid)
    if cart is None:
        raise HTTPException(404, "cart not found")

    cart_items = []
    price = 0.0
    for link in db.query(CartItemModel).filter_by(cart_id=cid).all():
        item = db.get(ItemModel, link.item_id)
        cart_items.append({
            "id": link.item_id, "name": item.name,
            "quantity": link.quantity,
            "available": item.deleted == False
        })

        price += item.price * link.quantity

    return {
        "id": cid,
        "items": cart_items,
        "price": price
    }


def dump_item(item):
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }


@app.post("/cart", status_code=201)
def post_cart(response: Response, db=Depends(get_db)):
    cart = CartModel()
    db.add(cart)
    db.commit()
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{id}")
def get_cart(id: int, db=Depends(get_db)):
    return create(db, id)


@app.get("/cart")
def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
    db=Depends(get_db),
):
    result = []

    for cart in db.query(CartModel).order_by(CartModel.id).all():
        cid = cart.id
        cart = create(db, cid)
        quantity = 0
        for item in cart["items"]:
            quantity += item["quantity"]

        print(cid, cart["price"], quantity)

        if min_price is not None and cart["price"] < min_price:
            continue
        if max_price is not None and cart["price"] > max_price:
            continue

        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset:offset+limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int, db=Depends(get_db)):
    link = db.get(CartItemModel, (cart_id, item_id))
    if link is not None:
        link.quantity += 1
    else:
        db.add(CartItemModel(cart_id=cart_id, item_id=item_id, quantity=1))
    db.commit()
    return create(db, cart_id)


@app.post("/item", status_code=201)
def post_item(body: Item, db=Depends(get_db)):
    item = ItemModel(name=body.name, price=body.price, deleted=False)
    db.add(item)
    db.commit()
    return dump_item(item)


@app.get("/item/{id}")
def get_item(id: int, db=Depends(get_db)):
    item = db.get(ItemModel, id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")
    return dump_item(item)


@app.get("/item")
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
    db=Depends(get_db),
):
    result = []
    for item in db.query(ItemModel).order_by(ItemModel.id).all():
        item = dump_item(item)
        if item["deleted"] == True and show_deleted == False:
            continue
        if min_price is not None and item["price"] < min_price:
            continue
        if max_price is not None and item["price"] > max_price:
            continue

        result.append(item)
    return result[offset:offset + limit]


@app.put("/item/{id}")
def put_item(id: int, body: Item, db=Depends(get_db)):
    item = db.get(ItemModel, id)
    if item is None:
        raise HTTPException(404, "not found")

    item.name = body.name
    item.price = body.price
    db.commit()
    return dump_item(item)


@app.patch("/item/{id}")
def patch_item(id: int, body: dict, db=Depends(get_db)):
    item = db.get(ItemModel, id)

    for key in body.keys():
        if key not in ["name", "price"]:
            raise HTTPException(422, "unknown field")

    if item.deleted:
        raise HTTPException(304)

    if "name" in body:
        item.name = body["name"]
    if "price" in body:
        item.price = body["price"]
    db.commit()
    return dump_item(item)


@app.delete("/item/{id}")
def delete_item(id: int, db=Depends(get_db)):
    item = db.get(ItemModel, id)
    item.deleted = True
    db.commit()
    return dump_item(item)
