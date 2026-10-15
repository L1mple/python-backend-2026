import os
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Float, ForeignKey, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

engine = create_engine(
    os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3307/hw4_db")
)


class Base(DeclarativeBase):
    pass


class ItemDb(Base):
    __tablename__ = "shop_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class CartDb(Base):
    __tablename__ = "shop_carts"

    id: Mapped[int] = mapped_column(primary_key=True)


class CartItemDb(Base):
    __tablename__ = "shop_cart_items"

    cart_id: Mapped[int] = mapped_column(ForeignKey("shop_carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("shop_items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(default=0)


Base.metadata.create_all(engine)

app = FastAPI(title="Shop API")


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


def to_item(item: ItemDb) -> Item:
    return Item(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


def build_cart(session: Session, cart_id: int) -> Cart:
    rows = session.execute(
        select(ItemDb, CartItemDb.quantity)
        .join(CartItemDb, CartItemDb.item_id == ItemDb.id)
        .where(CartItemDb.cart_id == cart_id)
    ).all()

    items = [
        CartItem(id=i.id, name=i.name, quantity=q, available=not i.deleted)
        for i, q in rows
    ]
    price = sum(i.price * q for i, q in rows)

    return Cart(id=cart_id, items=items, price=price)


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response):
    with Session(engine) as session:
        cart = CartDb()
        session.add(cart)
        session.commit()
        response.headers["location"] = f"/cart/{cart.id}"
        return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> Cart:
    with Session(engine) as session:
        if session.get(CartDb, cart_id) is None:
            raise HTTPException(HTTPStatus.NOT_FOUND)

        return build_cart(session, cart_id)


@app.get("/cart")
def get_cart_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
) -> list[Cart]:
    with Session(engine) as session:
        cart_ids = session.scalars(select(CartDb.id).order_by(CartDb.id)).all()
        carts = [build_cart(session, cart_id) for cart_id in cart_ids]

    if min_price is not None:
        carts = [c for c in carts if c.price >= min_price]
    if max_price is not None:
        carts = [c for c in carts if c.price <= max_price]

    if min_quantity is not None:
        carts = [c for c in carts if sum(i.quantity for i in c.items) >= min_quantity]
    if max_quantity is not None:
        carts = [c for c in carts if sum(i.quantity for i in c.items) <= max_quantity]

    return carts[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int) -> Cart:
    with Session(engine) as session:
        if session.get(CartDb, cart_id) is None or session.get(ItemDb, item_id) is None:
            raise HTTPException(HTTPStatus.NOT_FOUND)

        cart_item = session.get(CartItemDb, (cart_id, item_id))
        if cart_item is None:
            session.add(CartItemDb(cart_id=cart_id, item_id=item_id, quantity=1))
        else:
            cart_item.quantity += 1
        session.commit()

        return build_cart(session, cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(body: ItemCreate) -> Item:
    with Session(engine) as session:
        item = ItemDb(name=body.name, price=body.price, deleted=False)
        session.add(item)
        session.commit()

        return to_item(item)


@app.get("/item/{item_id}")
def get_item(item_id: int) -> Item:
    with Session(engine) as session:
        item = session.get(ItemDb, item_id)

        if item is None or item.deleted:
            raise HTTPException(HTTPStatus.NOT_FOUND)

        return to_item(item)


@app.get("/item")
def get_item_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
) -> list[Item]:
    query = select(ItemDb).order_by(ItemDb.id)

    if not show_deleted:
        query = query.where(ItemDb.deleted == False)
    if min_price is not None:
        query = query.where(ItemDb.price >= min_price)
    if max_price is not None:
        query = query.where(ItemDb.price <= max_price)

    with Session(engine) as session:
        items = session.scalars(query.offset(offset).limit(limit)).all()
        return [to_item(i) for i in items]


@app.put("/item/{item_id}")
def put_item(item_id: int, body: ItemCreate) -> Item:
    with Session(engine) as session:
        item = session.get(ItemDb, item_id)
        if item is None:
            raise HTTPException(HTTPStatus.NOT_FOUND)

        item.name = body.name
        item.price = body.price
        session.commit()

        return to_item(item)


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatch):
    with Session(engine) as session:
        item = session.get(ItemDb, item_id)
        if item is None:
            raise HTTPException(HTTPStatus.NOT_FOUND)

        if item.deleted:
            return Response(status_code=HTTPStatus.NOT_MODIFIED)

        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        session.commit()

        return to_item(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int):
    with Session(engine) as session:
        item = session.get(ItemDb, item_id)

        if item is not None:
            item.deleted = True
            session.commit()

        return {"id": item_id, "deleted": True}
